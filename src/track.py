import sys

from src.pipeline.default_modules import LongiSegSegmentModule, ITKRegistrationModule, TrackingModule
from src.pipeline.pipeline_architecture import *
from src.util import directory_arg

def add_registration(pipeline: Pipeline, source_config: Configuration) -> Configuration:
    segmentation = LongiSegSegmentModule()
    segmentation.set_config(no_tta = True, fold=0, trainer="nnUNetTrainerNoLongi", dataset_name="Dataset012_msLarge", configuration="3d_fullres") #fast segmentation
    segmentation_config = segmentation.get_configurations()[0]
    pipeline.add_configuration(segmentation_config, (0, source_config))

    registration = ITKRegistrationModule()
    registration_config = registration.get_configuration("Register with preceding image")
    pipeline.add_configuration(registration_config, (0, source_config), (1, segmentation_config))

    return registration_config

def get_pipeline(folder: Path, registration_needed: bool = True) -> Pipeline:
    pipeline = Pipeline()
    source = ImageFolderSource()
    source.set_config(folder = folder, sort_by="(?<=_)[^_.]+(?=\\.)")
    source_config = source.get_configurations()[0]
    pipeline.add_configuration(source_config)
    images_config = source_config
    if registration_needed:
        images_config = add_registration(pipeline, source_config)

    segmentation = LongiSegSegmentModule()
    segmentation.set_config(trainer="LongiSegTrainerDiffWeighting", dataset_name="Dataset012_msLarge", configuration="3d_fullres", folds=0)
    segmentation_config = segmentation.get_configurations()[0]
    pipeline.add_configuration(segmentation_config, (0, images_config))

    tracker = TrackingModule()
    tracker_config = tracker.get_configurations()[0]
    pipeline.add_configuration(tracker_config, (0, segmentation_config), (1, images_config))

    return pipeline

def get_single_track_pipeline(image_folder: Path, segmentations_folder: Path) -> Pipeline:
    pipeline = Pipeline()

    images = ImageFolderSource()
    images.set_config(folder = image_folder, sort_by="(?<=_)[^_.]+(?=\\.)")
    images_config = images.get_configurations()[0]
    pipeline.add_configuration(images_config)

    segmentation = ImageFolderSource()
    segmentation.set_config(folder = segmentations_folder, sort_by="(?<=_)[^_.]+(?=\\.)")
    segmentation_config = segmentation.get_configurations()[0]
    pipeline.add_configuration(segmentation_config)

    tracker = TrackingModule()
    tracker_config = tracker.get_configurations()[0]
    pipeline.add_configuration(tracker_config, (0, segmentation_config), (1, images_config))

    return pipeline

def get_parser():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_folder", type=path_arg, required=True, help="Input folder for data")
    parser.add_argument("-si", "--segmentations_folder", type=path_arg, default=None, help="Input folder for data")
    parser.add_argument("-o", "--output_folder", type=directory_arg, required=True, help="Output folder for data")
    parser.add_argument("-r", "--register", action="store_true", help="Register each image with preceding image")
    return parser

if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args(sys.argv[1:])
    GLOBAL_SETTINGS.set(dict(final_output_folder = args.output_folder,
                              temp_output_folder = args.output_folder / 'temp',
                              module_output_folder = args.output_folder / 'module_output'))
    pipeline = get_pipeline(args.input_folder, registration_needed = args.register) if args.segmentations_folder is None else get_single_track_pipeline(args.input_folder, args.segmentations_folder)
    pipeline.execute() #hope
