"""MiniMax H3 DMAD + Long Scenes workflow nodes: the pass 2 prompt for the chunked second pass and the song /
built-in audio switch.

The chunked second pass, the learned latent upscaler and the memory unload node of that workflow are part of
comfyui-vrgamedevgirl (the Video Builder pack) and are not repeated here.
"""

from .audio_mode import NODE_CLASS_MAPPINGS as _AUDIO_NODES, NODE_DISPLAY_NAME_MAPPINGS as _AUDIO_NAMES
from .pass2_prompt import NODE_CLASS_MAPPINGS as _PROMPT_NODES, NODE_DISPLAY_NAME_MAPPINGS as _PROMPT_NAMES

NODE_CLASS_MAPPINGS = {**_PROMPT_NODES, **_AUDIO_NODES}
NODE_DISPLAY_NAME_MAPPINGS = {**_PROMPT_NAMES, **_AUDIO_NAMES}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
