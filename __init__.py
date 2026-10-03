"""Standalone VRGDG optional node packs for ComfyUI."""
import importlib
import logging

_PACKS = (
    "face_fix",
    "general_utilities",
    "llm_nodes",
    "long_video",
    "lora_training",
    "ltx_minimax_tools",
    "music_audio",
    "ui_tools",
)

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

for _name in _PACKS:
    try:
        _module = importlib.import_module(f".optional_nodes.{_name}", package=__name__)
    except ImportError as _error:
        logging.warning("[VRGDG CustomNodePack] %s unavailable: %s. See README.md for dependencies.", _name, _error)
        continue
    NODE_CLASS_MAPPINGS.update(_module.NODE_CLASS_MAPPINGS)
    NODE_DISPLAY_NAME_MAPPINGS.update(_module.NODE_DISPLAY_NAME_MAPPINGS)

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
