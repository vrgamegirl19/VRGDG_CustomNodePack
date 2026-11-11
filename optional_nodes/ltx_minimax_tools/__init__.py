"""VRGDG LTX and MiniMax H3 sampling tools: CFG and sigma guiders, first/last-frame guides, IC ingredients grid, looping sampler, sigma presets, MiniMax connected chunks, still images, continuation trimming, the upscaler control panel, and the DMAD + Long Scenes workflow nodes (pass 2 prompt, song / built-in audio switch)."""
import importlib

_MODULES = (
    ".CustomLTXNodes",
    ".VRGDG_LTXFirstLastGuide",
    ".VRGDG_LTXICIngredientsGrid",
    ".VRGDG_LTXLoopingSampler",
    ".LTX25SigmaPreset",
    ".VRGDG_MiniMaxH3ConnectedChunks",
    ".MinimaxUpscaler",
    ".VRGDG_MiniMaxH3StillImage",
    ".VRGDG_MiniMaxH3TrimContinuation",
    ".MiniMaxH3LongScene",
)

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
for _name in _MODULES:
    _module = importlib.import_module(_name, package=__name__)
    NODE_CLASS_MAPPINGS.update(getattr(_module, "NODE_CLASS_MAPPINGS", {}))
    NODE_DISPLAY_NAME_MAPPINGS.update(getattr(_module, "NODE_DISPLAY_NAME_MAPPINGS", {}))

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
