"""H3 two-pass nodes that work without the Video Builder: the chunked second pass and the model unload before decode."""

import os

import comfy.model_management
import folder_paths
import nodes

from .h3_standalone_pass2_core import run_chunks


if "latent_upscale_models" not in folder_paths.folder_names_and_paths:
    folder_paths.add_model_folder_path("latent_upscale_models", os.path.join(folder_paths.models_dir, "latent_upscale_models"))


class AnyType(str):
    def __ne__(self, other):
        return False


any_typ = AnyType("*")


class _LearnedUpscaler:
    def upscale(self, latent: dict, settings: dict, scale: float) -> tuple:
        backend = nodes.NODE_CLASS_MAPPINGS.get("MinimaxH3LatentUpscalerNode3D")
        if backend is None:
            raise RuntimeError("Install LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler for the learned upscale.")
        return backend().run(latent, settings["path"], scale, settings["device"], settings["precision"])


class VRGDG_H3StandalonePass2:
    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {
            "latent": ("LATENT",),
            "model": ("MODEL",),
            "conditioning": ("CONDITIONING",),
            "sampler": ("SAMPLER",),
            "sigmas": ("SIGMAS",),
            "upscale_model_name": (folder_paths.get_filename_list("latent_upscale_models"),),
            "device": (["cuda", "cpu"],),
            "precision": (["bf16", "fp16", "fp32"],),
            "scale": ("FLOAT", {"default": 2.0, "min": 1.0, "max": 4.0, "step": 0.1}),
            "chunk_seconds": ("FLOAT", {"default": 3.0, "min": 0.1, "max": 120.0, "step": 0.1}),
            "overlap_seconds": ("FLOAT", {"default": 1.6, "min": 0.0, "max": 30.0, "step": 0.1}),
            "overlap_mode": (["locked", "crossfade"],),
            "seed": ("INT", {"default": 42, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                              "control_after_generate": True}),
            "tail_trim_seconds": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 10.0, "step": 0.1}),
            "max_window_tokens": ("INT", {"default": 0, "min": 0, "max": 2000000, "step": 1000}),
            "upscale": (["per_window", "whole_clip"],),
        }}

    RETURN_TYPES = ("LATENT", "STRING")
    RETURN_NAMES = ("refined_av_latent", "chunk_report")
    FUNCTION = "sample"
    CATEGORY = "VRGDG/MiniMax H3"
    DESCRIPTION = "H3 pass two in overlapping windows with the Builder's window planning, overlap and tail trimming. No Builder required."

    def sample(self, latent: dict, model: object, conditioning: list, sampler: object,
               sigmas: object, upscale_model_name: str, device: str, precision: str,
               scale: float, chunk_seconds: float, overlap_seconds: float, overlap_mode: str,
               seed: int, tail_trim_seconds: float, max_window_tokens: int, upscale: str) -> tuple:
        if upscale_model_name not in folder_paths.get_filename_list("latent_upscale_models"):
            raise ValueError("Select an installed checkpoint in latent_upscale_models.")
        if device not in ("cuda", "cpu") or precision not in ("bf16", "fp16", "fp32"):
            raise ValueError("Select a supported upscaler device and precision.")
        path = folder_paths.get_full_path_or_raise("latent_upscale_models", upscale_model_name)
        settings = {"path": path, "device": device, "precision": precision}
        return run_chunks(latent, model, conditioning, settings, _LearnedUpscaler(), sampler, sigmas,
                          scale, chunk_seconds, overlap_seconds, overlap_mode, seed,
                          tail_trim_seconds=tail_trim_seconds, max_window_tokens=max_window_tokens,
                          upscale_mode=upscale)


class VRGDG_H3StandaloneUnloadModels:
    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"value": (any_typ,)}}

    RETURN_TYPES = (any_typ,)
    FUNCTION = "unload"
    CATEGORY = "VRGDG/MiniMax H3"
    DESCRIPTION = "Offloads resident models from VRAM after the last pass, before the final video VAE decode."

    @classmethod
    def IS_CHANGED(cls, **kwargs) -> float:
        # A cached sampler output can be decoded again; the unload must still run before that decode.
        return float("nan")

    def unload(self, value: object) -> tuple:
        comfy.model_management.unload_all_models()
        comfy.model_management.soft_empty_cache()
        return (value,)


NODE_CLASS_MAPPINGS = {
    "VRGDG_H3StandalonePass2": VRGDG_H3StandalonePass2,
    "VRGDG_H3StandaloneUnloadModels": VRGDG_H3StandaloneUnloadModels,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "VRGDG_H3StandalonePass2": "H3 Chunked Pass 2 - Standalone (VRGDG)",
    "VRGDG_H3StandaloneUnloadModels": "H3 Unload Models Before Decode (VRGDG)",
}
