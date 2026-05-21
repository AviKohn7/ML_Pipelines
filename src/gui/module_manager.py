import dearpygui.dearpygui as dpg
from src.pipeline.pipeline_architecture import modules as pipeline_modules, Module as PipelineModule
import src.pipeline.default_modules
from typing import List, Tuple, Any

class Module:
    def __init__(self, pipeline_module_class: type[PipelineModule]):
        self.pipeline_module = pipeline_module_class()
        self.name = self.pipeline_module.name
        self.config_options = [config.name for config in self.pipeline_module.get_configurations()]
        self.current_config_index = 0
        
        self._all_configs_io = []
        for config in self.pipeline_module.get_configurations():
            inputs = []
            for i, input_type in enumerate(config.input_types):
                # Try to get a more meaningful name if available, otherwise use generic
                input_name = f"Input {i+1}" # Default
                # If the function has annotations, we might be able to get parameter names
                # This is a more advanced step, for now, stick to generic
                inputs.append((input_name, str(input_type)))
            
            outputs = []
            if config.output is not None:
                # If the output is a tuple, it means multiple outputs
                if hasattr(config.output, '__origin__') and config.output.__origin__ is Tuple:
                    for i, output_type in enumerate(config.output.__args__):
                        outputs.append((f"Output {i+1}", str(output_type)))
                else:
                    outputs.append(("Output", str(config.output)))
            self._all_configs_io.append({"inputs": inputs, "outputs": outputs})

        self.inputs = []
        self.outputs = []
        self._update_inputs_outputs()

        self.node_id = None # DPG node ID when placed in editor
        self.input_attr_ids = {} # DPG attribute ID -> (type, name)
        self.output_attr_ids = {} # DPG attribute ID -> (type, name)

    def _update_inputs_outputs(self):
        io_data = self._all_configs_io[self.current_config_index]
        self.inputs = io_data["inputs"]
        self.outputs = io_data["outputs"]

    def get_display_name(self):
        return self.name

    def get_config_options(self):
        return self.config_options

    def get_current_config(self):
        return self.config_options[self.current_config_index]

    def set_current_config(self, config_name):
        if config_name in self.config_options:
            self.current_config_index = self.config_options.index(config_name)
            self.pipeline_module.set_config(config_name=config_name) # Update pipeline module's config
            self._update_inputs_outputs() # Update inputs/outputs based on new config
        else:
            print(f"Warning: Config '{config_name}' not found for module '{self.name}'")

    def get_inputs_for_display(self):
        displayed_inputs = []
        for name, type_str in self.inputs:
            display_type = type_str.replace("Transport", "").replace("DataTransport", "")
            displayed_inputs.append(f"{name} ({display_type})")
        return displayed_inputs

    def get_outputs_for_display(self):
        displayed_outputs = []
        for name, type_str in self.outputs:
            display_type = type_str.replace("Transport", "").replace("DataTransport", "")
            displayed_outputs.append(f"{name} ({display_type})")
        return displayed_outputs

    def get_input_types(self):
        return [type_str for _, type_str in self.inputs]

    def get_output_types(self):
        return [type_str for _, type_str in self.outputs]

    def execute(self, inputs: dict):
        """
        Executes the wrapped pipeline module's current configuration function.
        'inputs' will be a dictionary mapping input names to data.
        Returns a dictionary mapping output names to data.
        """
        current_config = self.pipeline_module.get_configurations()[self.current_config_index]
        
        # Prepare arguments for the pipeline module's function
        args = []
        for i, (input_name, _) in enumerate(self.inputs):
            args.append(inputs.get(input_name)) # Assuming inputs dict keys match input_name

        result = current_config.function(*args)

        outputs = {}
        if current_config.output is not None:
            # If the output is a tuple, it means multiple outputs
            if isinstance(result, tuple):
                for i, res_item in enumerate(result):
                    outputs[f"Output {i+1}"] = res_item
            else:
                outputs["Output"] = result
        return outputs

class ModuleManager:
    def __init__(self):
        self.available_modules = {} # name -> Module object
        self.module_categories = {} # category -> [Module objects]
        self._load_pipeline_modules()

    def _load_pipeline_modules(self):
        for category, module_classes in pipeline_modules.items():
            self.module_categories[category] = []
            for module_class in module_classes:
                gui_module = Module(module_class)
                self.available_modules[gui_module.name] = gui_module
                self.module_categories[category].append(gui_module)

    def register_module(self, module: Module):
        self.available_modules[module.name] = module

    def get_module_names(self):
        return list(self.available_modules.keys())

    def get_module(self, name):
        return self.available_modules.get(name)

# Global module manager instance
module_manager = ModuleManager()
