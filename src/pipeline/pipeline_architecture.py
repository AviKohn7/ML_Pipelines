from __future__ import annotations

from argparse import Namespace
from collections import defaultdict, deque
from typing import Union, Optional, Type, Any
from uuid import uuid4

from pipeline_util import *
from src.pipeline.data_types import Regex
from src.util import regex_arg, path_arg
from contextvars import ContextVar

#todo: add a structure object representing the required folder structure of the DataTransport, including file exts allowed
#todo: add required config option
#todo: add deserialization for all config types. Current types: List, Path, Regex
#todo: optional inputs for pipeline
#todo: add functionality for removing configuration from pipeline
#todo: add functionality for selecting which values to save and which not to keep as temp. Not enough to j use sink

string_mappers = {
    Path: path_arg
}

GLOBAL_SETTINGS = ContextVar("Settings") #this allows for scalability and future multithreading
GLOBAL_SETTINGS.set({
    "final_output_folder": None, #where the final output is returned
    "module_output_folder": None, #where the result of each module's output is returned
    "temp_output_folder": None #for any temporary output needed during calculation
})


class Configuration:
    """
    A unique configuration for a Module instance. This represents the configuration that that module is in
    """
    def __init__(self, name: str, function: Callable, module: Module, *input_types: Type, output_type: Type = None, **irrelevant_config: Type):
        self.name = name
        self.id = module.id
        self.function = function
        self.input_types = input_types
        self.output = output_type
        self.config_types = Namespace(**{key: value for key, value in vars(module.config_types) if key not in irrelevant_config})
        self.config = module.config

class ConfigError(ValueError):
    def __init__(self, message: str):
        super().__init__(message)
class Module:
    def __init__(self, name):
        self.uuid = uuid4()
        self.name = name
        self.config_types = Namespace()
        self.config = Namespace()
        self._add_config_options(save_output=bool)
        self.set_config(save_output=False)

    def get_configurations(self) -> List[Configuration]:
        ...
    def get_configuration(self, name: str) -> Configuration:
        configs = self.get_configurations()
        result =  next(name == config.name for config in configs)
        if result is None:
            raise ValueError(f"{name} is not a valid configuration for module {self.name}. Allowed configurations are: {(config.name for config in configs)}")
        return result
    def create_configuration(self, name: str, function: Callable, *input_types: Type, output: Type = None, **irrelevant_config: Type) -> Configuration:
        return Configuration(name, function, self, *input_types,
                             output_type=output, **irrelevant_config)


    def set_config(self, **kwargs):
        for key, value in kwargs.items():
            try:
                mapped_value = self._get_true_type(value, getattr(self.config_types, key))
                setattr(self.config, key, mapped_value)
            except Exception as e:
                raise ValueError(f"Invalid input {value}", e)
    
    def destroy(self):
        ...
    
    def _get_true_type(self, value, type):
        if isinstance(value, type):
            return value
        elif type in string_mappers:
            return string_mappers[type](value)
        else:
            return type(value)

    def _add_config_options(self, **kwds):
        for key, value in kwds.items():
            setattr(self.config_types, key, value)
            setattr(self.config, key, None)


    def _module_folder(self) -> Path:
        return GLOBAL_SETTINGS.get()["module_output_folder"]

    def _temp_folder(self) -> Path:
        return GLOBAL_SETTINGS.get()["temp_output_folder"]

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self.id = value + self.uuid
            
    
#To be used in a UI
class Pipeline:
    def _Node(self, configuration: Configuration) -> Namespace:
        return Namespace(inputs=[None] * len(configuration.input_types), outputs=set())

    def __init__(self):
        self.configurations = dict()
        self.sources = set() #add nodes with no inputs

    def add_configuration(self, configuration: Configuration, *inputs: Tuple[int, Configuration]):
        for index, input in inputs:
            if input not in self.configurations.keys():
                raise ValueError(f"All inputs given must already be in the pipeline, input {input.name} at {index} is not")
            if not isinstance(input.output, configuration.input_types[index]):
                raise ValueError(
                    f"Input {input.name} at {index} has an output of type {input.output}, but {configuration.input_types[index]} is required")
            if configuration in self.configurations and self.configurations[configuration].inputs[index] is not None:
                raise ValueError(
                    f"Can't add input at index {index}, index is already filled")

        if configuration not in self.configurations:
            self.configurations[configuration] = self._Node(configuration)

        for index, input in inputs:
            self.configurations[input].outputs.add((configuration, index))
            self.configurations[configuration].inputs[index] = input

        if len(configuration.input_types) == 0:
            self.sources.add(configuration)

    def has_cycle(self):
        visited = set()
        def DFSUtil(v):
            visited.add(v)
            # Recur for all the vertices adjacent to this vertex
            for neighbor, index in self.configurations[v].outputs:
                if neighbor in visited or DFSUtil(neighbor):
                    return True
            return False

        for elem in self.configurations.keys():
            if elem not in visited:
                if DFSUtil(elem):
                    return True
        return False

    def all_inputs_filled(self):
        for elem in self.configurations.keys():
            if None in self.configurations[elem].inputs:
                return False
        return True


    def execute(self):
        if self.has_cycle():
            raise ValueError("Cycle detected, can't execute with cycle")
        if not self.all_inputs_filled():
            raise ValueError("No all inputs are filled")
        if len(self.sources) == 0:
            raise ValueError("Must be at least one source. Also, bug in DFS code or source adding code bc this should have been caught")

        output_folder = GLOBAL_SETTINGS.get()["final_output_folder"]
        module_output_folder = GLOBAL_SETTINGS.get()["module_output_folder"]
        temp_output_folder = GLOBAL_SETTINGS.get()["temp_output_folder"]

        if output_folder is None or module_output_folder is None or temp_output_folder is None:
            raise ValueError("Output folder, module output folder, or temp folder are not set")

        def _Value():
            return Namespace(inputs_filled = 0, output=None)
        values = defaultdict(_Value)
        sinks = set()

        available_nodes = deque()
        available_nodes.extend(self.sources)

        while len(available_nodes) > 0:
            node = available_nodes.popleft()
            inputs = self.configurations[node].inputs
            input_values = [values[input].output for input in inputs]

            output = self._run_configuration(node, input_values, output_folder, module_output_folder, temp_output_folder)
            values[node].output = output

            for output_node, index in self.configurations[node].outputs:
                values[output_node].inputs_filled += 1
                if values[output_node].inputs_filled == len(output_node.input_types):
                    available_nodes.append(output_node)

            if len(self.configurations[node].outputs) == 0:
                sinks.add(node)

    def _run_configuration(self, node: Configuration, input_values: List[DataTransport], output_folder: Path, module_output_folder: Path, temp_output_folder: Path):
        GLOBAL_SETTINGS.set({
            "final_output_folder": output_folder / node.id,
            "module_output_folder": module_output_folder / node.id,
            "temp_output_folder": temp_output_folder / node.id,
        })
        return node.function(*input_values) #assume input validation is already done when creating pipeline,
        # any issues will just be errors



class Source(Module):
    def get_data(self) -> DataTransport:
        raise NotImplementedError("Use a child module, this doesn't exist")

class FolderSource(Source):
    def __init__(self):
        super().__init__("Source")
        self._add_config_options(folder = Path,
                                 filter_by = regex_arg,
                                 sort_by = regex_arg,
                                 extensions = List)
    def get_data(self) -> DataTransport:
        if self.config.folder is None:
            raise ConfigError("Must include data folder")
        transport = FolderDataTransport(True, Path(self.config_types.folder), extensions=self.config_types.extensions)
        try:
            return transport.sorted(lambda x: int(re.search(self.config_types.sort_by, str(x)).group()))
        except Exception as e:
            raise ValueError(f"Can't sort folder based on regex. Do all files with that extension match the regex?")
    def get_configurations(self) -> List[Configuration]:
        return [self.create_configuration("Patient source", self.get_data, output=DataTransport)]

class SegmentModule(Module):
    def __init__(self):
        super().__init__("Segmentation")
    def segment(self, data: ImageDataTransport) -> ImageDataTransport:
        raise NotImplementedError("Use a child module, this doesn't exist")
    def get_configurations(self) -> List[Configuration]:
        return [self.create_configuration("Basic Segmentation", self.segment,ImageDataTransport, output=ImageDataTransport)]

class RegistrationModule(Module):
    def __init__(self):
        super().__init__("Registration")

    def get_initial_objects(self):
        ...
    def get_image(self, path):
        ...
    def _register(self, fixed_image, moving_image, fixed_mask, moving_mask, initial_object) -> Any:
        ...
    def save_image(self, image, path):
        ...
    def get_mask(self, path):
        return self.get_image(path)

    def register_with_preceding(self, data: ImageDataTransport, mask: ImageDataTransport | None = None) -> ImageDataTransport:
        """
        Register all images with the image before it.
        :param data:
        :param mask:
        :return:
        :raises: ValueError if the two DataTransport's structures don't match
        """
        initial_object = self.get_initial_objects()
        output_folder = self._module_folder()

        data_paths = data.get_file_paths()
        mask_paths = mask.get_file_paths() if mask is not None else None
        fixed_image = self.get_image(data_paths[0])
        fixed_mask = self.get_mask(mask_paths[0]) if mask_paths is not None else None
        self.save_image(fixed_image, output_folder / data_paths[0].name)

        for i in range(1, len(data_paths)):
            moving_image = self.get_image(data_paths[i])
            moving_mask = self.get_mask(mask_paths[i]) if mask_paths is not None else None
            result = self._register(fixed_image, moving_image, fixed_mask, moving_mask, initial_object)
            fixed_image, fixed_mask = result, moving_mask
            self.save_image(result, output_folder / data_paths[0].name)
        return ImageFolderTransport(False, output_folder, structure_of=data)
    def register_with_first(self, data: ImageDataTransport, mask: ImageDataTransport | None = None) -> ImageDataTransport:
        """
        Register all images with the first image in the data transport
        :param data:
        :param mask:
        :return:
        :raises: ValueError if the two DataTransport's structures don't match
        """
        ...
        initial_object = self.get_initial_objects()
        output_folder = self._module_folder()

        data_paths = data.get_file_paths()
        mask_paths = mask.get_file_paths() if mask is not None else None
        fixed_image = self.get_image(data_paths[0])
        fixed_mask = self.get_mask(mask_paths[0]) if mask_paths is not None else None
        self.save_image(fixed_image, output_folder / data_paths[0].name)

        for i in range(1, len(data_paths)):
            moving_image = self.get_image(data_paths[i])
            moving_mask = self.get_mask(mask_paths[i]) if mask_paths is not None else None
            result = self._register(fixed_image, moving_image, fixed_mask, moving_mask, initial_object)
            self.save_image(result, output_folder / data_paths[0].name)
        return ImageFolderTransport(False, output_folder, structure_of=data)

    def register_with_given(self, fixed_image: Path | str, data: ImageDataTransport, fixed_mask: Path | str | None = None, mask: ImageDataTransport | None = None) -> ImageDataTransport:
        """
        Register all images with the given fixed image
        :param fixed_image:
        :param data:
        :param fixed_mask:
        :param mask:
        :return:
        :raises: ValueError if the two DataTransport's structures don't match
        """
        initial_object = self.get_initial_objects()
        output_folder = self._module_folder()

        data_paths = data.get_file_paths()
        mask_paths = mask.get_file_paths() if mask is not None else None
        fixed_image = self.get_image(fixed_image)
        fixed_mask = self.get_mask(fixed_mask) if fixed_mask is not None else None

        for i in range(len(data_paths)):
            moving_image = self.get_image(data_paths[i])
            moving_mask = self.get_mask(mask_paths[i]) if mask_paths is not None else None
            result = self._register(fixed_image, moving_image, fixed_mask, moving_mask, initial_object)
            self.save_image(result, output_folder / data_paths[0].name)
        return ImageFolderTransport(False, output_folder, structure_of=data)

    def get_configurations(self):
        return [
            self.create_configuration("Register with preceding image", self.register_with_preceding, ImageDataTransport,
                          ImageDataTransport, output=ImageDataTransport),
            self.create_configuration("Register with first image", self.register_with_first, ImageDataTransport,
                          ImageDataTransport, output=ImageDataTransport),
            self.create_configuration("Register with other image", self.register_with_given, Union[Path, str], ImageDataTransport,
                          Union[Path, str, None], Optional[ImageDataTransport], output=ImageDataTransport),
        ]
