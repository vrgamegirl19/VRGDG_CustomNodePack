"""VRGDG MiniMax: a one-button node that opens a simple text / image / reference to video studio."""

from aiohttp import web
from server import PromptServer

from .minimax_studio_core import (MAX_REFERENCE_IMAGES, advanced_settings, build_prompt, model_choices, model_defaults,
                                  requirements)


class VRGDG_MiniMaxStudio:
    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {}}

    RETURN_TYPES = ()
    FUNCTION = "noop"
    CATEGORY = "VRGDG/MiniMax H3"
    DESCRIPTION = "Click VRGDG MiniMax to make one MiniMax H3 video from text, a start image or reference images."

    def noop(self) -> tuple:
        return ()


NODE_CLASS_MAPPINGS = {"VRGDG_MiniMaxStudio": VRGDG_MiniMaxStudio}
NODE_DISPLAY_NAME_MAPPINGS = {"VRGDG_MiniMaxStudio": "VRGDG MiniMax"}


@PromptServer.instance.routes.get("/vrgdg/minimax_studio/options")
async def vrgdg_minimax_studio_options(request):
    return web.json_response({"ok": True, "defaults": model_defaults(), "choices": model_choices(),
                              "max_reference_images": MAX_REFERENCE_IMAGES, "advanced": advanced_settings(),
                              **requirements()})


@PromptServer.instance.routes.post("/vrgdg/minimax_studio/build")
async def vrgdg_minimax_studio_build(request):
    try:
        prompt = build_prompt(await request.json())
    except ValueError as error:
        return web.json_response({"ok": False, "error": str(error)}, status=400)
    return web.json_response({"ok": True, "prompt": prompt})
