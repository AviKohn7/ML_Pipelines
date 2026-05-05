from __future__ import annotations

import functools
import heapq

import itk
from itk.itkMeanSquaresImageToImageMetricv4Python import itkMeanSquaresImageToImageMetricv4IF3IF3 as itkMeanSquaresImageToImageMetricv4
import torch
from longiseg.inference.predict_from_raw_data_longi import LongiSegPredictor
from longiseg.utilities.file_path_utilities import get_output_folder

from pipeline_architecture import *
from scipy.ndimage import label, center_of_mass
from enum import StrEnum

from longiseg.training.LongiSegTrainer.nnUNetTrainerNoLongi import nnUNetTrainerNoLongi
from longiseg.training.LongiSegTrainer.LongiSegTrainer import LongiSegTrainer
from longiseg.training.LongiSegTrainer.variants.longitudinal.LongiSegTrainerDiffWeighting import LongiSegTrainerDiffWeighting

from longiseg.inference import predict_from_raw_data_longi

from src.util import bounded_int, bounded_float, value_set_arg, safe_remove_tree
import json

class LongiSegSegmentModule(SegmentModule):
    def __init__(self):
        super().__init__()
        self.name = "LongiSeg Segment"
        self._add_config_options(plans=str, folds=List,
                                 configuration=str,
                                 dataset_name=str,
                                 trainer=str,
                                 step_size=functools.partial(bounded_float, min=0, max=1),
                                 disable_tta=bool, save_probabilities=bool, npp=int, nps=int,
                                 device=value_set_arg('cuda', 'cpu', 'mps'))
    #per-patient segment
    def segment(self, segmentations: ImageDataTransport) -> ImageDataTransport:
        config = self.config
        model_folder = get_output_folder(config.dataset_name, config.trainer, config.plans, config.configuration)
        if config.device == 'cpu':
            # let's allow torch to use hella threads
            import multiprocessing
            torch.set_num_threads(multiprocessing.cpu_count())
            device = torch.device('cpu')
        elif config.device == 'cuda':
            # multithreading in torch doesn't help LongiSeg if run on GPU
            torch.set_num_threads(1)
            torch.set_num_interop_threads(1)
            device = torch.device('cuda')
        else:
            device = torch.device('mps')
        predictor = LongiSegPredictor(tile_step_size=config.step_size,
                                      use_gaussian=True,
                                      use_mirroring=not config.disable_tta,
                                      perform_everything_on_device=True,
                                      device=device,
                                      verbose=False,
                                      verbose_preprocessing=False,
                                      allow_tqdm=False)
        predictor.initialize_from_trained_model_folder(
            model_folder,
            config.folds
        )
        folder = segmentations.get_folder_path()
        output_folder = self._module_folder()
        patient_file = self.get_patient_file(segmentations, self._temp_folder())
        #todo: make sure that this actually works with registration output
        predictor.predict_patients(str(folder), str(output_folder), patient_file,
                               save_probabilities=False,
                               overwrite=True,
                               num_processes_preprocessing=config.npp,
                               num_processes_segmentation_export=config.nps,
                               folder_with_segs_from_prev_stage=None,
                               num_parts=1,
                               part_id=0)


        return ImageFolderTransport(False, output_folder, structure_of=segmentations)

    def get_patient_file(self, segmentations: ImageDataTransport, output_folder: Path = None) -> str:
        folder = segmentations.get_folder_path()
        output_folder = output_folder or folder

        path_names = [p.stem for p in segmentations.get_file_paths()]
        patient_tr = {
            folder.stem: path_names
        }
        file_path = str(output_folder / "generated_patients.json")

        with open(file_path, "w") as f:
            json.dump(patient_tr, f)
        return file_path

    def destroy(self):
        ...

    def get_configurations(self) -> List[Configuration]:
        return [self.create_configuration("Per-patient Segmentation", self.segment,ImageDataTransport, output=ImageDataTransport)]

#todo: add option for parameter file
class ITKRegistrationModule(RegistrationModule):
    def __init__(self):
        super().__init__()
        self.name = "ITK Registration"
        self._add_config_options(parameter_maps_names=List[str],
                                 resolutions=int)

    def get_parameter_object(self):
        parameter_object = itk.ParameterObject.New()

        resolutions = self.config.resolutions
        for name in self.config.parameter_maps_names():
            parameter_map = itk.ParameterObject.GetDefaultParameterMap(name, resolutions)
            parameter_object.AddParameterMap(parameter_map)
        return parameter_object


    def get_image(self, path):
        return itk.imread(path, itk.F)

    def get_mask(self, path):
        return itk.imread(path, itk.F)

    def get_initial_objects(self):
        return self.get_parameter_object()

    def save_image(self, image, path):
        itk.imwrite(image, path)

    def _register(self, fixed_image, moving_image, fixed_mask, moving_mask, initial_object) -> Any:
        result, transform = itk.elastix_registration_method(
            fixed_image,
            moving_image,
            parameter_object=initial_object,
            fixed_mask=fixed_mask,
            moving_mask=moving_mask,
            log_to_console=False,
        )
        return result


class ChangeType(StrEnum):
    GROW = 'Grow'
    SHRINK = 'Shrink'
    DISAPPEARED = 'Disappeared'
    NEW = 'New'
    MERGED = 'Merged'
    UNCHANGED = 'Unchanged'

class Status:
    def __init__(self, current_id, status: ChangeType, volume: float, prev_status: Status = None, prev_ids: int = None) -> None:
        self.id = current_id
        self.prev_ids: int = prev_ids
        self.status: ChangeType = status
        self.volume: float = volume #in mm^3
        self.percent_change_in_volume: float = volume / prev_status.volume if prev_status is not None else None
        self.actual_change_in_volume: float = volume - prev_status.volume if prev_status is not None else volume
    def __str__(self):
        return json.dumps({ #insertion order guaranteed via python 3.7+
            "id": self.id,
            "status": self.status,
            "volume": self.volume,
            "percent_change_in_volume": self.percent_change_in_volume,
            "actual_change_in_volume": self.actual_change_in_volume,
        })


#todo: remove output?
class TrackingModule(Module):
    def __init__(self):
        super().__init__("Tracking")
        #intensity_background_threshold is not inclusive
        self._add_config_options(intensity_background_threshold=float, size_change_threshold=float, max_movable_distance=floar)
        self.set_config(intensity_background_threshold=0, size_change_threshold=.1, max_movable_distance=50)

    def map(self, segmentations: ImageDataTransport, images: ImageDataTransport) -> DataTransport:
        structure = np.ones((3, 3))  # full connectivity, even diagonals
        states = {}
        state = None
        highest_id = 0

        segmentation_tuples = segmentations.get_data()
        metadatas = images.get_metadatas()
        images_tuples = images.get_data()

        prev_labeled, prev_feature_count, prev_centroids = None, None, None
        for segmentation_tuple, image_tuple, metadata in zip(segmentation_tuples, images_tuples, metadatas):
            segmentation, path = segmentation_tuple
            image, image_path = image_tuple
            image_path = Path(image_path)
            voxel_sizes = metadata.spacing

            labeled, feature_count, centroids = self.label_by_connected(segmentation[0], structure)
            if state is None: #first
                volumes = self.get_volume(labeled, voxel_sizes, feature_count)
                state = [Status(i+1, ChangeType.NEW, volumes[i], None) for i in range(len(volumes))]
                highest_id = len(volumes)
                states[image_path.stem] = state
            else:
                labeled, highest_id, state, removed_state = self.relabel(labeled, prev_labeled, centroids, prev_centroids,
                                              state, highest_id, image, voxel_sizes)
                states[image_path.stem] = removed_state + state

            ImageDataTransport.save_image(self._module_folder() / image_path.name, labeled, metadata)
            prev_labeled, prev_feature_count, prev_centroids = labeled, feature_count, centroids
        with open(self._module_folder() / "state_changes.json") as file:
            json.dump(states, file)

        return FolderDataTransport(False, self._module_folder())



    def label_by_connected(self, image: NDArray, structure = None, segmentation_value=1) -> Tuple[Any, int, Any]:
        image = (image == segmentation_value)
        labeled, num_features =  label(image, structure=structure)
        centroids = center_of_mass(image, labeled, range(1, num_features + 1))
        return labeled, num_features, centroids

    def get_volume(self, labeled, voxel_sizes, feature_count):
        voxel_volume = np.prod(voxel_sizes)  # in mm³
        volumes = {
            label: np.sum(labeled == label) * voxel_volume for label in range(1, feature_count + 1)
        }
        return volumes

    def get_single_volume(self, labeled, voxel_sizes, label):
        voxel_volume = np.prod(voxel_sizes)  # in mm³
        return np.sum(labeled == label) * voxel_volume

    def relabel(self, labeled, prev_labeled, centroids, prev_centroids, prev_states, highest_id, image: NDArray, spacing):
        image_path = (image > self.config.intensity_background_threshold)
        centroid_status, prev_centroid_status, highest_id = self.match_centroids(image_path, centroids, prev_centroids, prev_states, spacing, highest_id, prev_labeled)
        lookup = np.array([0] + [st.id for st in centroid_status])
        relabeled = labeled[lookup]
        return relabeled, highest_id, centroid_status, [status for status in prev_centroid_status if status.status == ChangeType.DISAPPEARED]


    def voxel_neighbors(self, shape, idx):
        for d in [(1, 0, 0), (-1, 0, 0),
                  (0, 1, 0), (0, -1, 0),
                  (0, 0, 1), (0, 0, -1)]:
            nxt = tuple(idx[i] + d[i] for i in range(3))
            if all(0 <= nxt[i] < shape[i] for i in range(3)):
                yield nxt, d

    def dijkstra_distance(self, mask, start, goals_set, spacing, max_mm):
        """
        Run Dijkstra from one start until all goals found or max distance exceeded.
        """
        spacing = np.array(spacing)

        pq = [(0.0, start)]
        visited = set()
        best = {}

        max_dist = max_mm

        while pq:
            cost, node = heapq.heappop(pq)

            if cost > max_dist:
                continue

            if node in visited:
                continue
            visited.add(node)

            if node in goals_set:
                best[node] = cost
                if len(best) == len(goals_set):
                    break

            for nxt, d in self.voxel_neighbors(mask.shape, node):
                if mask[nxt] == 0:
                    continue

                step = np.linalg.norm(np.array(d) * spacing)
                heapq.heappush(pq, (cost + step, nxt))

        return best

    # -----------------------------
    # Main matching function
    # -----------------------------
    def match_centroids(self, mask,
                        centroids,
                        prev_centroids,
                        states,
                        spacing,
                        highest_id,
                        prev_labeling,
                        max_mm=50.0) -> Tuple[List[Status], List[Status], int]:
        """
        Returns:
            centroid_status
            prev_centroid_status
        """

        centroids = [tuple(map(int, c)) for c in centroids]
        prev_centroids = [tuple(map(int, c)) for c in prev_centroids]

        unmatched_centroids = set(range(len(centroids)))
        unmatched_prev = set(range(len(prev_centroids)))

        matches = []
        dist_map = {}

        # -----------------------------
        # Precompute distances
        # -----------------------------
        for j, pc in enumerate(prev_centroids):
            reachable = self.dijkstra_distance(
                mask,
                pc,
                set(centroids),
                spacing,
                max_mm
            )

            for i, c in enumerate(centroids):
                if c in reachable:
                    dist_map[(i, j)] = reachable[c]

        # -----------------------------
        # Greedy matching
        # -----------------------------
        sorted_pairs = sorted(dist_map.items(), key=lambda x: x[1])

        match_map = {}  # i -> j

        for (i, j), d in sorted_pairs:
            if i in unmatched_centroids and j in unmatched_prev:
                match_map[i] = j
                unmatched_centroids.remove(i)
                unmatched_prev.remove(j)

        # -----------------------------
        # OUTPUT STRUCTURES
        # -----------------------------
        centroid_status: List[Status] = [None] * len(centroids)
        prev_centroid_status : List[Status] = [None] * len(prev_centroids)

        # -----------------------------
        # Matched (CONTINUED)
        # -----------------------------
        for i, j in match_map.items():
            prev_state = states[j]

            centroid_status[i] = Status(
                current_id=prev_state.id,
                status=ChangeType.UNCHANGED,
                volume=self.get_single_volume(prev_labeling, spacing, i+1),
                prev_status=prev_state
            )
            if centroid_status[i].percent_change_in_volume >= 1 + self.config.size_change_threshold:
                centroid_status[i].status = ChangeType.GROW

            if centroid_status[i].percent_change_in_volume <= 1 - self.config.size_change_threshold:
                centroid_status[i].status = ChangeType.SHRINK

            prev_centroid_status[j] = prev_state

        # -----------------------------
        # NEW centroids
        # -----------------------------
        for i in unmatched_centroids:
            highest_id += 1
            centroid_status[i] = Status(
                current_id=highest_id,
                status=ChangeType.NEW,
                volume=self.get_single_volume(prev_labeling, spacing, i+1),
                prev_status=None
            )

        # -----------------------------
        # DISAPPEARED prev centroids
        # -----------------------------
        for j in unmatched_prev:
            prev_state = states[j]

            prev_centroid_status[j] = Status(
                current_id=prev_state.id,
                status=ChangeType.DISAPPEARED,
                volume=0,
                prev_status=prev_state
            )

        return centroid_status, prev_centroid_status, highest_id

    def get_configurations(self):
        return [
            self.create_configuration("Track marked objects", self.map, SortedDataTransport,
                          SortedDataTransport, output=DataTransport)
        ]