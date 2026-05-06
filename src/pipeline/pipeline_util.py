from __future__ import annotations

import warnings
from typing import List, Set, Callable, Tuple, Generator
from pathlib import Path
import re
import os
from dataclasses import dataclass
import itk
import numpy as np
from PIL import Image
from numpy.typing import NDArray
import nibabel as nib

FOLDER_SEPARATOR = "__--__"
DEFAULT_IMAGE_EXTENSIONS = set({".nii", ".nii.gz", ".mha", ".mhd", ".nrrd", ".png", ".jpg", ".tif", ".tiff"})
class Structure:
    def __init__(self, struct_to_copy = None):
        self.data = dict()
        self.data_in_order = []
        if struct_to_copy is not None:
            self.data = dict(**struct_to_copy.data)
            self.data_in_order = list(struct_to_copy.data_in_order)
    def add_path_string(self, path: str):
        path_str = self._path_to_str(path)
        if path_str not in self.data:
            self.data[path_str] = len(self.data_in_order)
            self.data_in_order.append(path_str)

    def add_directory(self, path, extensions : Set[str] = None):
        extensions = extensions or DEFAULT_IMAGE_EXTENSIONS
        for dir_, _, files in os.walk(path):
            for file_name in files:
                if extensions is None or file_name.endswith(tuple(extensions)):
                    rel_file = Path(dir_).relative_to(path) / file_name
                    rel_file_str = str(rel_file)
                    self.add_path_string(rel_file_str)
    def sorted(self, key_extractor: Callable[[str], int]) -> Structure:
        new_structure = Structure()
        new_structure.data_in_order = sorted(self.data_in_order, key=lambda s: key_extractor(self._str_to_path_str(s)))
        new_structure.data = {}
        for i, elem in enumerate(new_structure.data_in_order):
            new_structure.data[elem] = i
        return new_structure
    def sort_extractor(self, path: Path) -> int:
        return self.data[self._path_to_str(path)]
    def get_mapping(self, data: "Structure") -> dict[str, str]:
        ...
    def files_identical(self, other):
        if not isinstance(other, Structure):
            return False
        return self.data.keys() == other.data.keys()

    @staticmethod
    def _path_to_str(path: Path | str) -> str:
        if isinstance(path, Path):
            path = str(path)
        return re.sub("[/\\\\]", FOLDER_SEPARATOR, path)

    @staticmethod
    def _str_to_path_str(s: str) -> str:
        return re.sub(FOLDER_SEPARATOR, "/", s)
    def __eq__(self, other):
        if not isinstance(other, Structure):
            return False
        return self.data_in_order == other.data_in_order

class DataTransport:
    def __init__(self, is_user_input: bool):
        self.is_user_input = is_user_input

    def sorted(self, sort_key_extractor: Callable[[str], int] = None) -> "DataTransport":
        raise NotImplementedError("Use child classes of DataTransport, this should be overridden in all children")

    def get_data(self) -> Generator[Tuple[NDArray, str]]:
        raise NotImplementedError("Use child classes of DataTransport, this should be overridden in all children")

    def get_file_paths(self) -> List[Path]:
        raise NotImplementedError("Use child classes of DataTransport, this should be overridden in all children")

    def get_folder_path(self) -> Path:
        raise NotImplementedError("Use child classes of DataTransport, this should be overridden in all children")
    def get_structure(self) -> Structure:
        """
        Get the structure of the data in this DataTransport
        :return:
        """
        raise NotImplementedError("Use child classes of DataTransport, this should be overridden in all children")
    def augment_structure(self, obj: "DataTransport"):
        """
        Change structure of this object to match input object.
        :param obj:
        :return:
        :raises: ValueError if files don't match 1-1
        """
        ...
        
    def destroy_object(self):
        ...

    @staticmethod
    def get_image_from_file(image_path) -> NDArray:
        img = itk.imread(image_path)
        return  itk.array_from_image(img)

@dataclass
class ImageMetadata:
    spacing: List[float]
    origin: List[float]
    direction: List[List[float]]

class ImageDataTransport(DataTransport):
    def get_metadatas(self) -> List[ImageMetadata]:
        return [self._get_voxel_metadata(p) for p in self.get_file_paths()]

    @staticmethod
    def _get_voxel_metadata(path) -> ImageMetadata:
        ext = "".join(path.suffixes).lower()

        itk_formats = {".nii", ".nii.gz", ".mha", ".mhd", ".nrrd", ".tif", ".tiff"}

        # Formats with no meaningful spacing
        no_spacing = {".png", ".jpg", ".jpeg"}

        # --- No spacing formats ---
        if ext in no_spacing:
            return ImageMetadata([1,1], [0,0], [0,0])

        # --- ITK-supported formats ---
        if ext in itk_formats:
            try:
                img = itk.imread(str(path))
                spacing = list(img.GetSpacing())
                origin = list(img.GetOrigin())
                direction = np.array(img.GetDirection(), dtype=float).tolist()
                return ImageMetadata(spacing, origin, direction)
            except ValueError:
                warnings.warn("Could not read spacing from {} using itk, defaulting to unit spacing".format(path))

        # --- Fallback ---
        return ImageMetadata([1,1,1], [0,0,0], [0,0,0])

    @staticmethod
    def save_image(path, image: NDArray, metadata: ImageMetadata):
        new_img = itk.image_from_array(image)
        new_img.SetSpacing(metadata.spacing)
        new_img.SetOrigin(metadata.origin)

        direction_array = np.array(metadata.direction, dtype=float)
        direction_matrix = itk.matrix_from_array(direction_array)
        new_img.SetDirection(direction_matrix)

        itk.imwrite(new_img, path)

class FolderDataTransport(DataTransport):
    def __init__(self, is_user_input: bool, folder_path: Path, extensions: Set[str] = None, structure_of: DataTransport =None):
        super().__init__(is_user_input)
        if not folder_path.is_dir():
            raise ValueError("FolderDataTransport requires an existing folder as input")
        self.folder_path = folder_path
        self.extensions = extensions
        self.structure = Structure()
        self.structure.add_directory(self.folder_path, DEFAULT_IMAGE_EXTENSIONS)
        if structure_of is not None:
            self.augment_structure(structure_of)

    def sorted(self, sort_key_extractor: Callable[[str], int] = None) -> "FolderDataTransport":
        new_structure = self.structure.sorted(sort_key_extractor)
        return type(self)(self.is_user_input, self.folder_path, self.extensions, new_structure)

    def get_data(self) -> Generator[Tuple[NDArray, str]]:
        paths = self.get_file_paths() #in order
        return ((DataTransport.get_image_from_file(p), str(p)) for p in paths)

    def get_file_paths(self) -> List[Path]:
        paths = [p for p in Path(self.folder_path).rglob("*")
                 if p.is_file() and (self.extensions is None or p.name.lower().endswith(tuple(self.extensions)))]
        paths.sort(key=lambda p: self.structure.sort_extractor(p.relative_to(self.folder_path)))
        return paths

    def get_folder_path(self) -> Path:
        return self.folder_path #todo: folder can't match structure. Fine?

    def get_structure(self) -> Structure:
        return self.structure

    def augment_structure(self, obj: "DataTransport"):
        super().augment_structure(obj)
        structure_to_copy = obj if isinstance(obj, Structure) else obj.get_structure()
        if not self.structure.files_identical(structure_to_copy):
            raise ValueError(f"Can't augment structure unless identical files. This has {self.structure.data_in_order} while the input has {structure_to_copy.data_in_order}" )
        self.structure = Structure(structure_to_copy)

class ImageFolderTransport(FolderDataTransport, ImageDataTransport):
    def __init__(self, is_user_input: bool, folder_path: Path, extensions: Set[str] = None, structure_of: DataTransport=None):
        extensions = extensions or DEFAULT_IMAGE_EXTENSIONS
        super().__init__(is_user_input, folder_path, extensions, structure_of)