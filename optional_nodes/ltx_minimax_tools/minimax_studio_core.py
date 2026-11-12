"""Fills the batched H3 two-pass API templates from the VRGDG MiniMax studio settings."""

import copy
import json
import os

import folder_paths
import nodes

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows", "api")
TEMPLATES = {
    "text_to_video": "H3_Batched_ImageToVideo_API.json",
    "image_to_video": "H3_Batched_ImageToVideo_API.json",
    "reference_to_video": "H3_Batched_RefToVideo_API.json",
}
# MiniMaxH3ReferenceToVideo accepts ref_image_0 .. ref_image_8.
MAX_REFERENCE_IMAGES = 9
# setting -> (node id, input name, model folder)
MODEL_FIELDS = {
    "diffusion_model": ("141", "model_name", "diffusion_models"),
    "text_encoder": ("128", "clip_name", "text_encoders"),
    "video_vae": ("119", "vae_name", "vae"),
    "audio_vae": ("120", "vae_name", "vae"),
    "pass1_lora": ("9201", "lora_name", "loras"),
    "refiner_lora": ("207", "lora_name", "loras"),
    "upscaler": ("9502", "upscale_model_name", "latent_upscale_models"),
}

# Advanced settings: (setting, label, node id, input name), grouped like the Video Builder's two-pass panel.
ADVANCED = (
    ("Pass 1 · low resolution", (
        ("pass1_steps", "Steps", "124", "steps"),
        ("pass1_denoise", "Denoise", "124", "denoise"),
        ("pass1_sampler", "Sampler", "123", "sampler_name"),
        ("pass1_scheduler", "Scheduler", "124", "scheduler"),
        ("pass1_lora_strength", "DMAD LoRA strength", "9201", "strength_model"),
        ("pass1_shift_video", "Sigma shift, video", "9401", "shift_video"),
        ("pass1_shift_audio", "Sigma shift, audio", "9401", "shift_audio"),
        ("ref_image_size", "Reference image size", "136", "ref_image_size"),
    )),
    ("Pass 2 · upscale and refine", (
        ("upscale_scale", "Latent upscale ×", "185", "value"),
        ("pass2_steps", "Steps", "190", "value"),
        ("pass2_denoise", "Denoise", "191", "value"),
        ("pass2_sampler", "Sampler", "210", "sampler_name"),
        ("pass2_scheduler", "Scheduler", "192", "scheduler"),
        ("refiner_strength", "Refiner LoRA strength", "207", "strength_model"),
        ("upscale_mode", "Upscale", "9502", "upscale"),
        ("upscaler_device", "Upscaler device", "9502", "device"),
        ("upscaler_precision", "Upscaler precision", "9502", "precision"),
    )),
    ("Pass 2 · windows", (
        ("chunk_seconds", "Window (s)", "9502", "chunk_seconds"),
        ("overlap_seconds", "Overlap (s)", "9502", "overlap_seconds"),
        ("overlap_mode", "Overlap mode", "9502", "overlap_mode"),
        ("tail_trim_seconds", "Tail trim (s)", "9502", "tail_trim_seconds"),
        ("max_window_tokens", "Max window tokens (0 = off)", "9502", "max_window_tokens"),
    )),
    ("Model loading", (
        ("weight_dtype", "Weight dtype", "141", "weight_dtype"),
        ("sage_attention", "Sage attention", "141", "sage_attention"),
        ("fp16_accumulation", "fp16 accumulation", "141", "enable_fp16_accumulation"),
    )),
    ("Output", (
        ("crf", "Video quality (CRF, lower is better)", "142", "crf"),
    )),
)
ADVANCED_FIELDS = {key: (node, name) for _, fields in ADVANCED for key, _, node, name in fields}

CUSTOM_NODES = (
    {"name": "ComfyUI (latest)", "url": "https://github.com/comfyanonymous/ComfyUI",
     "nodes": ("MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo", "MiniMaxH3SigmaShift", "ComfyMathExpression")},
    {"name": "ComfyUI-KJNodes", "url": "https://github.com/kijai/ComfyUI-KJNodes", "nodes": ("DiffusionModelLoaderKJ",)},
    {"name": "ComfyUI-VideoHelperSuite", "url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite", "nodes": ("VHS_VideoCombine",)},
    # VRGDG_H3StandalonePass2 calls this node; the pack's Aug 28 update renamed it to MinimaxH3LatentUpscaler3D.
    {"name": "Comfyui_Minimax_h3_latent_Upscaler", "url": "https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler",
     "nodes": ("MinimaxH3LatentUpscalerNode3D",), "renamed_to": "MinimaxH3LatentUpscaler3D"},
)

_HF = "https://huggingface.co/"
_COMFY_H3 = _HF + "Comfy-Org/MiniMax-H3/resolve/main/"
_SINGULARITY = _HF + "WarmBloodAban/Minimax-h3_Singularity/resolve/main/"
# Download choices per model setting; the first is recommended. "also" lists older names of the same file.
MODEL_SOURCES = {
    "fl2va": ("Video model", [
        {"label": "Official fl2va, pruned int8", "file": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "size": "21 GB",
         "url": _COMFY_H3 + "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"},
        {"label": "Official fl2va, int8", "file": "minimax_h3_fl2va_int8_convrot.safetensors", "size": "34 GB",
         "url": _COMFY_H3 + "diffusion_models/minimax_h3_fl2va_int8_convrot.safetensors"},
    ]),
    "ref2va": ("Video model", [
        {"label": "Singularity v2, int8", "file": "Minimax-h3_Singularity_ref2va_v2_int8.safetensors", "size": "34 GB",
         "url": _SINGULARITY + "Minimax-h3_Singularity_ref2va_v2_int8.safetensors"},
        {"label": "Singularity v2, pruned int8", "file": "Minimax-h3_Singularity_ref2va_v2_pruned_int8.safetensors", "size": "21 GB",
         "url": _SINGULARITY + "Minimax-h3_Singularity_ref2va_v2_pruned_int8.safetensors"},
        {"label": "Official ref2va, pruned int8", "file": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "size": "21 GB",
         "url": _COMFY_H3 + "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"},
    ]),
    "text_encoder": ("Text encoder", [
        {"label": "Qwen3-VL 32B, nvfp4", "file": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "size": "15.7 GB",
         "url": _COMFY_H3 + "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"},
        {"label": "Qwen3-VL 32B, int8", "file": "qwen3vl_32b_minimax_h3_int8_convrot.safetensors", "size": "27.1 GB",
         "url": _COMFY_H3 + "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"},
    ]),
    "video_vae": ("Video VAE", [
        {"label": "Video VAE, fp16", "file": "minimax_h3_video_vae_fp16.safetensors", "size": "5.2 GB",
         "url": _COMFY_H3 + "vae/minimax_h3_video_vae_fp16.safetensors"},
    ]),
    "audio_vae": ("Audio VAE", [
        {"label": "Audio VAE, fp32", "file": "minimax_h3_audio_vae_fp32.safetensors", "size": "605 MB",
         "url": _COMFY_H3 + "vae/minimax_h3_audio_vae_fp32.safetensors"},
    ]),
    "pass1_lora": ("Pass 1 LoRA", [
        {"label": "DMAD 4-step", "file": "dmad_minimax_h3_4step_full_critic_comfyui.safetensors", "size": "1.96 GB",
         "url": _HF + "ZhengmingYu/DMAD/resolve/main/minimax_h3/dmad_minimax_h3_4step_full_critic_comfyui.safetensors"},
    ]),
    "refiner_lora": ("Pass 2 refiner LoRA", [
        {"label": "Open Regenerate 2K refiner", "file": "minimax_h3_open_regenerate_2k_refiner_rank_16_bf16.safetensors", "size": "155 MB",
         "url": _HF + "Kijai/MiniMax-H3-experimental/resolve/main/loras/minimax_h3_open_regenerate_2k_refiner_rank_16_bf16.safetensors"},
    ]),
    "upscaler": ("Latent upscaler", [
        {"label": "LBH 3D v1, bf16", "file": "minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors", "size": "691 MB",
         "also": ("minimax_h3_latent_upscaler_3d_bf16.safetensors",),
         "url": _HF + "LBH-123-AI/Minimax_h3_latent_Upscaler/resolve/main/minimax_h3_latent_upscaler_3d_conv_v1/minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors"},
    ]),
}


def load_template(mode: str) -> dict:
    if mode not in TEMPLATES:
        raise ValueError(f"Unknown mode {mode!r}; pick text_to_video, image_to_video or reference_to_video.")
    with open(os.path.join(TEMPLATE_DIR, TEMPLATES[mode]), encoding="utf-8") as handle:
        return json.load(handle)


def model_defaults() -> dict:
    """The template's model file for every model setting, per mode."""
    result = {}
    for mode in TEMPLATES:
        prompt = load_template(mode)
        result[mode] = {key: prompt[node]["inputs"][name] for key, (node, name, _) in MODEL_FIELDS.items()}
    return result


def model_choices() -> dict:
    folders = {folder for _, _, folder in MODEL_FIELDS.values()}
    return {folder: folder_paths.get_filename_list(folder) for folder in sorted(folders)}


def _input_spec(class_type: str, name: str) -> dict:
    """kind, options and limits of a node input, read from the installed node; {} when the node is not installed
    or the input is a dynamic widget (VHS format options)."""
    node_class = nodes.NODE_CLASS_MAPPINGS.get(class_type)
    if node_class is None:
        return {}
    types = node_class.INPUT_TYPES()
    entry = types.get("required", {}).get(name) or types.get("optional", {}).get(name)
    if entry is None:
        return {}
    extra = entry[1] if len(entry) > 1 else {}
    if isinstance(entry[0], (list, tuple)):
        return {"kind": "combo", "options": list(entry[0])}
    if entry[0] == "COMBO":
        return {"kind": "combo", "options": list(extra.get("options", []))}
    spec = {"kind": entry[0]}
    spec.update({k: extra[k] for k in ("min", "max", "step") if k in extra})
    return spec


def _value_kind(value: object) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    return "INT" if isinstance(value, int) else "FLOAT" if isinstance(value, float) else "STRING"


def advanced_settings() -> list:
    """The advanced setting groups with each field's kind, choices and the template value per mode (None when the
    mode's workflow does not have that input)."""
    templates = {mode: load_template(mode) for mode in TEMPLATES}
    groups = []
    for title, fields in ADVANCED:
        rows = []
        for key, label, node, name in fields:
            defaults = {mode: prompt[node]["inputs"].get(name) if node in prompt else None
                        for mode, prompt in templates.items()}
            value = next(v for v in defaults.values() if v is not None)
            class_type = next(p[node]["class_type"] for p in templates.values() if node in p and name in p[node]["inputs"])
            spec = _input_spec(class_type, name) or {"kind": _value_kind(value)}
            rows.append({"key": key, "label": label, "defaults": defaults, **spec})
        groups.append({"title": title, "fields": rows})
    return groups


def _advanced_value(class_type: str, name: str, value: object, current: object) -> object:
    """``value`` as the node input expects it; the template's ``current`` value decides the type for dynamic inputs."""
    spec = _input_spec(class_type, name) or {"kind": _value_kind(current)}
    kind = spec["kind"]
    if kind == "combo":
        if value not in spec["options"]:
            raise ValueError(f"{value!r} is not an option for {name}.")
        return value
    if kind == "BOOLEAN":
        return bool(value)
    if kind == "INT":
        return int(value)
    if kind == "FLOAT":
        return float(value)
    return str(value)


def source_key(mode: str, key: str) -> str:
    if key == "diffusion_model":
        return "ref2va" if mode == "reference_to_video" else "fl2va"
    return key


def requirements() -> dict:
    """Which custom nodes and model files are installed, with download links for each mode's models."""
    custom_nodes = []
    for pack in CUSTOM_NODES:
        item = {"name": pack["name"], "url": pack["url"],
                "installed": all(name in nodes.NODE_CLASS_MAPPINGS for name in pack["nodes"])}
        if not item["installed"] and pack.get("renamed_to") in nodes.NODE_CLASS_MAPPINGS:
            item["note"] = "Your version renamed the node VRGDG H3 Standalone Pass 2 calls; it needs the version from before Aug 28, 2026."
        custom_nodes.append(item)
    installed = {folder: set(files) for folder, files in model_choices().items()}
    models = {}
    for mode in TEMPLATES:
        rows = []
        for key, (_, _, folder) in MODEL_FIELDS.items():
            label, sources = MODEL_SOURCES[source_key(mode, key)]
            options = []
            for source in sources:
                found = next((name for name in (source["file"], *source.get("also", ())) if name in installed[folder]), None)
                options.append({**{k: v for k, v in source.items() if k != "also"}, "installed_as": found})
            rows.append({"key": key, "label": label, "folder": folder, "options": options})
        models[mode] = rows
    return {"custom_nodes": custom_nodes, "models": models}


def _input_image(name: str) -> str:
    if not folder_paths.exists_annotated_filepath(name):
        raise ValueError(f"Image not found in ComfyUI/input: {name}")
    return name


def build_prompt(settings: dict) -> dict:
    """An API prompt for one video from the studio settings."""
    mode = settings.get("mode")
    prompt = copy.deepcopy(load_template(mode))
    images = list(settings.get("images") or [])
    seed = int(settings.get("seed", 1))

    prompt["138"]["inputs"]["value"] = str(settings.get("prompt", ""))
    prompt["132"]["inputs"]["value"] = float(settings.get("duration", 10))
    prompt["115"]["inputs"]["value"] = int(settings.get("width", 1920))
    prompt["184"]["inputs"]["value"] = int(settings.get("height", 1088))
    prompt["129"]["inputs"]["noise_seed"] = seed
    prompt["9502"]["inputs"]["seed"] = seed
    for key, value in (settings.get("advanced") or {}).items():
        if key not in ADVANCED_FIELDS:
            raise ValueError(f"Unknown advanced setting {key!r}.")
        node, name = ADVANCED_FIELDS[key]
        if node in prompt and name in prompt[node]["inputs"]:
            inputs = prompt[node]["inputs"]
            inputs[name] = _advanced_value(prompt[node]["class_type"], name, value, inputs[name])
    prompt["142"]["inputs"]["filename_prefix"] = f"VRGDG_MiniMax/{mode}"

    models = settings.get("models") or {}
    for key, (node, name, folder) in MODEL_FIELDS.items():
        value = models.get(key)
        if not value:
            continue
        if value not in folder_paths.get_filename_list(folder):
            raise ValueError(f"{value} is not in the {folder} model folder.")
        prompt[node]["inputs"][name] = value

    conditioning = prompt["136"]["inputs"]
    if mode == "image_to_video":
        if len(images) != 1:
            raise ValueError("Image to video needs one start image.")
        prompt["301"]["inputs"]["image"] = _input_image(images[0])
    elif mode == "text_to_video":
        del prompt["301"]
        del conditioning["first_frame"]
    else:
        if len(images) > MAX_REFERENCE_IMAGES:
            raise ValueError(f"Reference to video takes up to {MAX_REFERENCE_IMAGES} images.")
        for node in ("301", "302"):
            del prompt[node]
        for key in [key for key in conditioning if key.startswith("ref_images.")]:
            del conditioning[key]
        for index, name in enumerate(images):
            node = f"ref_image_{index}"
            prompt[node] = {"class_type": "LoadImage", "inputs": {"image": _input_image(name)},
                            "_meta": {"title": f"<Picture {index + 1}>"}}
            conditioning[f"ref_images.ref_image_{index}"] = [node, 0]
    return prompt
