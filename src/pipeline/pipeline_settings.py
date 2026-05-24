

from contextvars import ContextVar
from pathlib import Path
from attr import dataclass


@dataclass
class Settings:
    final_output_folder: Path
    module_output_folder: Path
    temp_output_folder: Path

GLOBAL_SETTINGS = ContextVar("Settings") #this allows for scalability and future multithreading
GLOBAL_SETTINGS.set(Settings(
    final_output_folder=None,
    module_output_folder=None,
    temp_output_folder=None
))

def get_temp_folder() -> Path:
    return GLOBAL_SETTINGS.get().temp_output_folder

def get_module_folder() -> Path:
    return GLOBAL_SETTINGS.get().temp_output_folder

def get_final_output_folder() -> Path:
    return GLOBAL_SETTINGS.get().final_output_folder

def set_global_settings(final_output_folder: Path, module_output_folder: Path, temp_output_folder: Path):
    GLOBAL_SETTINGS.set(Settings(
        final_output_folder=final_output_folder,
        module_output_folder=module_output_folder,
        temp_output_folder=temp_output_folder
    ))