"""Write the MiniMax H3 DMAD + Long Scenes 2 Pass workflow from the Video Builder's own graph.

The Video Builder (comfyui-vrgamedevgirl) is asked for its 2 Pass graph with DMAD on and Long Scenes (pass 2 in
windows) on, for a sample 12 s Reference to Video scene with every other setting at its default. Nothing is rendered.
The compiled API graph is then turned into a canvas workflow: the Builder-only inputs become nodes a person fills in
(reference images, the song / built-in audio switch, the prompt), the project latent saves are dropped, and every
part gets a group and a note.

The workflow uses two VRGDG packs, and no node is in both:

- comfyui-vrgamedevgirl: ``BUILDER_NODES`` (the chunked second pass and the learned latent upscaler loader).
- this pack, ``MiniMaxH3LongScene/``: the pass 2 prompt and the three audio switch nodes.

Any other VRGDG node in the result stops the export, so a node that exists only in someone's local Builder copy
never reaches the shared workflow.

The canvas format needs each node's inputs and widgets. The script reads ``/object_info`` from a running ComfyUI
(``--server``, default http://127.0.0.1:8188) or from a saved copy (``--object-info``); the nodes in
``MiniMaxH3LongScene/`` are read from their classes. Run it with ComfyUI's Python, with comfyui-vrgamedevgirl
installed next to this pack (or pass ``--builder-pack``). From ``ComfyUI_windows_portable``::

    python_embeded\python.exe ComfyUI\custom_nodes\VRGDG_CustomNodePack\optional_nodes\ltx_minimax_tools\scripts\export_dmad_long_scene_workflow.py

Re-run it after the Builder's 2 Pass graph, DMAD or chunked second pass change, so the workflow stays in step.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import tempfile
import urllib.request
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

PACK = Path(__file__).resolve().parents[1]  # optional_nodes/ltx_minimax_tools
NODE_FOLDER = PACK / "MiniMaxH3LongScene"
OUTPUT = PACK / "workflows" / "MiniMaxH3_DMAD_LongScene_2Pass.json"
DEFAULT_BUILDER_PACK = PACK.parents[2] / "comfyui-vrgamedevgirl"  # ComfyUI/custom_nodes/comfyui-vrgamedevgirl
SCENE_SECONDS = 12.0
LOG_PREFIX = "[VRGDG Workflow Export]"

# The only Video Builder nodes the workflow may use. Both are on the Builder pack's GitHub main branch.
BUILDER_NODES = ("VRGDG_MiniMaxH3ChunkedPass2", "VRGDG_MiniMaxH3LatentUpscaleModelLoader")

ROOT = DEFAULT_BUILDER_PACK  # set by use_builder_pack()


def use_builder_pack(path: Path) -> None:
    """Import the Video Builder from ``path`` (a comfyui-vrgamedevgirl folder)."""
    global ROOT
    ROOT = Path(path).resolve()
    if not (ROOT / "runner" / "minimax_workflows.py").is_file():
        raise SystemExit(f"{LOG_PREFIX} comfyui-vrgamedevgirl was not found at {ROOT}. Pass --builder-pack.")
    if str(ROOT.parent) not in sys.path:
        sys.path.insert(0, str(ROOT.parent))

EXAMPLE_PROMPT = (
    "subject_definitions:\n"
    "<Subject 1> is the singer from the <Picture 1> character reference.\n"
    "<Picture 2> is the location reference.\n\n"
    "<Audio 1> is the complete synchronized song and vocal track.\n\n"
    "detailed_description:\n"
    "<Subject 1> performs on a rooftop at dusk, inside the location from <Picture 2>.\n\n"
    "[Shot 1] A slow push-in on a medium close-up of <Subject 1>: <Subject 1> sings in sync with the vocals in "
    "<Audio 1> from 0.5 s to 5.5 s, <d>[English, warm singing] first lyric line here</d>, delivered softly with "
    "natural lip and jaw movements.\n\n"
    "[Shot 2] At 00:06.000, continuing the same moment, same place and pose, the camera arcs to a medium shot as "
    "<Subject 1> sings in sync with the vocals in <Audio 1> from 6.0 s to 11.5 s, <d>[English, rising] second "
    "lyric line here</d>, one hand lifting from the side.\n\n"
    "overall_soundscape:\n"
    "<Audio 1> remains the sole complete soundtrack.\n"
)

# Frontend-only note node. Its single widget is the Markdown text.
NOTE_TYPE = "MarkdownNote"

GROUP_COLORS = ("#3f789e", "#8a6e3b", "#3e7e4e", "#6b4e8a", "#a1309b", "#2f7f7f", "#88413d", "#4b5a6b")


# --------------------------------------------------------------------------------------------------------------------
# 1. The Builder graph
# --------------------------------------------------------------------------------------------------------------------

def build_builder_graph() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The Builder's compiled DMAD + Long Scenes 2 Pass API graph for a sample scene, and its render payload."""
    from PIL import Image

    pkg = ROOT.name
    payload_mod = importlib.import_module(f"{pkg}.minimax.settings_payload")
    workflows = importlib.import_module(f"{pkg}.runner.minimax_workflows")
    models = importlib.import_module(f"{pkg}.runner.models")
    rules = importlib.import_module(f"{pkg}.runner.minimax_scene_rules")
    patches = importlib.import_module(f"{pkg}.runner.minimax_patches")

    temp = Path(tempfile.mkdtemp(prefix="vrgdg_workflow_export_"))
    picture = temp / "reference.png"
    Image.new("RGB", (64, 64), "gray").save(picture)
    audio = temp / "song.wav"
    with wave.open(str(audio), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\0\0" * 16000 * int(SCENE_SECONDS + 8))

    settings = payload_mod.normalize_minimax_h3_settings({"video_mode": "reference_to_video", "render_pass": "two_pass"})
    settings = payload_mod.set_minimax_h3_dmad(settings, True)
    settings.update({"two_pass_pass1_seed": 42, "two_pass_pass2_seed": 42, "seed": 42})
    payload = {
        **payload_mod.build_minimax_render_payload(settings),
        "prompt": EXAMPLE_PROMPT,
        "project_folder": str(temp),
        "audio_path": str(audio),
        "source_duration_seconds": SCENE_SECONDS + 8,
        "scene_number": 1,
        "timeline_start_seconds": 0,
        "timeline_end_seconds": SCENE_SECONDS,
        "scene_duration_seconds": SCENE_SECONDS,
        "image_paths": [str(picture), str(picture)],
    }
    # The sample scene is checked against the model folders and node list of this PC. Those do not matter for an
    # exported file, so every check passes; the workflow names the Builder's default files.
    installed = [
        payload_mod.DMAD_LORA_NAME, payload_mod.DMAD_REFINER_LORA_NAME,
        str(payload.get("diffusion_model_name") or "minimax_h3_ref2va_pruned_int8_convrot.safetensors"),
        str(payload.get("clip_name") or "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
        "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "minimax_h3_video_vae_fp16.safetensors", "minimax_h3_audio_vae_fp32.safetensors",
        "minimax_h3_latent_upscaler_3d_bf16.safetensors",
    ]
    nodes = {"MiniMaxChunkFeedForward": object, "MiniMaxH3SigmaShift": object, "BlockSparseAttention": object}
    with patch.object(models, "_folder_choices", return_value=installed), \
            patch.object(models, "_lora_choices", return_value=installed), \
            patch.object(rules, "_feedforward_available", return_value=True), \
            patch.object(patches, "_get_comfy_node_mappings", return_value=nodes):
        payload = rules.apply_minimax_h3_scene_rules(payload)
        built = workflows._build_minimax_h3_2pass_api_prompt(payload)
    if not (built.get("chunked_pass2") or {}).get("enabled"):
        raise RuntimeError(f"The sample scene did not get the chunked second pass: {built.get('chunked_pass2')}")
    return built["prompt"], payload


# --------------------------------------------------------------------------------------------------------------------
# 2. Turn it into the shareable graph
# --------------------------------------------------------------------------------------------------------------------

def _single(graph: Dict[str, Any], class_type: str, title_part: str = "") -> str:
    found = [key for key, node in graph.items() if node["class_type"] == class_type
             and title_part in node.get("_meta", {}).get("title", "")]
    if len(found) != 1:
        raise RuntimeError(f"Expected one {class_type} ({title_part!r}) in the Builder graph, found {found}.")
    return found[0]


def shareable_graph(api: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The Builder graph with person-filled inputs instead of Builder inputs. Keys become canvas node ids."""
    graph = json.loads(json.dumps(api))
    refs_id = _single(graph, "VRGDG_MiniMaxH3ReferenceMediaFromPaths")
    chunk_id = _single(graph, "VRGDG_MiniMaxH3ChunkedPass2")
    unload_ids = [key for key, node in graph.items() if node["class_type"] == "VRGDG_UnloadModelsBeforeDecode"]
    pass1_sampler = graph[chunk_id]["inputs"]["latent"]
    if graph[pass1_sampler[0]]["class_type"] == "VRGDG_MiniMaxH3SaveLatent":
        pass1_sampler = graph[pass1_sampler[0]]["inputs"]["latent"]
    pass2_text = graph[chunk_id]["inputs"]["conditioning"][0]
    pass2_text_id = graph[pass2_text]["inputs"]["prompt"][0]
    prompt_id = graph[_single(graph, "MiniMaxH3ReferenceToVideo", "MiniMax H3 Reference to Video")]["inputs"]["prompt"][0]

    # Project-only nodes: latent saves (the windows read pass 1 directly) and the Builder's reference list.
    for key in [key for key, node in graph.items() if node["class_type"] == "VRGDG_MiniMaxH3SaveLatent"]:
        graph.pop(key)
    graph.pop(refs_id)
    graph[chunk_id]["inputs"]["latent"] = list(pass1_sampler)

    # The Builder gates its final decode with an unload node (after a latent save); this workflow decodes the windows'
    # result directly.
    for unload_id in unload_ids:
        graph.pop(unload_id)
        for node in graph.values():
            for name, value in node["inputs"].items():
                if value == [unload_id, 0]:
                    node["inputs"][name] = [chunk_id, 0]

    # Reference pictures: two LoadImage nodes in the Builder's order (<Picture 1>, <Picture 2>).
    for index, (node_id, title) in enumerate((("301", "REFERENCE 1 - <Picture 1> (character)"),
                                              ("302", "REFERENCE 2 - <Picture 2> (location)"))):
        graph[node_id] = {"class_type": "LoadImage", "inputs": {"image": "example.png"}, "_meta": {"title": title}}
    for node in graph.values():
        for name in list(node["inputs"]):
            value = node["inputs"][name]
            if isinstance(value, list) and len(value) == 2 and value[0] == refs_id:
                if name == "ref_images.ref_image_0":
                    node["inputs"][name] = ["301", 0]
                elif name == "ref_images.ref_image_1":
                    node["inputs"][name] = ["302", 0]
                else:
                    node["inputs"].pop(name)

    # Pass 2 prompt: made from the pass 1 prompt by the same function the Builder uses.
    graph[pass2_text_id] = {
        "class_type": "VRGDG_MiniMaxH3Pass2PromptNoTiming",
        "inputs": {"prompt": [prompt_id, 0]},
        "_meta": {"title": "Pass 2 prompt (no lyric text, no times)"},
    }

    # Audio: one switch between your song (the graph above) and H3's built-in audio, which is the Builder's
    # built-in graph: no reference audio, pass 1 samples the plain latent, the soundtrack is decoded from pass 1.
    audio_id = _single(graph, "VHS_LoadAudio")
    drive_id = _single(graph, "VRGDG_MiniMaxH3AudioDrive")
    duration_id = _single(graph, "PrimitiveFloat", "Duration")
    graph[audio_id] = {
        "class_type": "VRGDG_MiniMaxH3AudioSource",
        "inputs": {"built_in_audio": False, "audio_file": "", "seek_seconds": 0.0, "duration": [duration_id, 0]},
        "_meta": {"title": "AUDIO - My song or built-in audio (switch)"},
    }
    drive = graph[drive_id]["inputs"]
    graph[drive_id] = {
        "class_type": "VRGDG_MiniMaxH3AudioLockSwitch",
        "inputs": {"av_latent": drive["av_latent"], "audio_vae": drive["audio_vae"],
                   "built_in_audio": [audio_id, 1], "song": [audio_id, 0]},
        "_meta": {"title": "Lock song (skipped for built-in audio)"},
    }
    graph["304"] = {
        "class_type": "VRGDG_MiniMaxH3VideoSoundtrack",
        "inputs": {"av_latent": list(pass1_sampler), "audio_vae": drive["audio_vae"],
                   "built_in_audio": [audio_id, 1], "song": [audio_id, 0]},
        "_meta": {"title": "Video soundtrack (song or built-in)"},
    }
    for node in graph.values():
        for name, value in node["inputs"].items():
            if value == [drive_id, 1]:
                node["inputs"][name] = ["304", 0]
    graph[prompt_id]["inputs"]["value"] = EXAMPLE_PROMPT
    graph[chunk_id]["_meta"]["title"] = "VRGDG H3 Chunked Pass 2 - refine in windows"
    graph["303"] = {"class_type": "PreviewAny", "inputs": {"source": [chunk_id, 1]},
                    "_meta": {"title": "Window report"}}

    save_id = _single(graph, "VHS_VideoCombine")
    graph[save_id]["inputs"]["filename_prefix"] = "VRGDG_H3_DMAD_LongScene"
    titles = {
        "BUILDER OUTPUT - Learned Latent Upscaled 1080p Video": "SAVE - Final Video",
        "Final Center Crop - Exact 1920x1080": "Final Resize - exact width x height",
        "Load LoRA": "PASS 2 - Refiner LoRA (DMAD)",
        "Extra MiniMax LoRA 1 - pass1": "PASS 1 - DMAD 4-step LoRA",
        "Low Resolution Generation": "PASS 1 - Sampler (low resolution)",
        "Basic Guider": "PASS 1 - Guider",
        "BasicScheduler": "PASS 1 - Scheduler (DMAD 4 steps)",
        "KSamplerSelect": "PASS 1 - Sampler (lcm)",
        "Pass 2 conditioning (windows)": "PASS 2 - Conditioning for the windows",
    }
    for node in graph.values():
        title = node.get("_meta", {}).get("title", "")
        title = titles.get(title, title)
        for prefix in ("BUILDER INPUTS - ", "BUILDER INPUT - ", "BUILDER OUTPUT - "):
            if title.startswith(prefix):
                title = "INPUT - " + title[len(prefix):]
        node.setdefault("_meta", {})["title"] = title
    _check_links(graph)
    _check_vrgdg_nodes(graph)
    return graph


def _check_vrgdg_nodes(graph: Dict[str, Any]) -> None:
    """Stop when the workflow would need a VRGDG node that is neither a known Builder node nor in this pack."""
    own = set(load_node_folder().NODE_CLASS_MAPPINGS)
    unknown = sorted({node["class_type"] for node in graph.values()
                      if node["class_type"].startswith("VRGDG_") and node["class_type"] not in own
                      and node["class_type"] not in BUILDER_NODES})
    if unknown:
        raise RuntimeError(
            f"The Builder graph now uses {unknown}. Check they are on the Builder pack's GitHub main branch, then add "
            "them to BUILDER_NODES, or replace them in shareable_graph()."
        )


def _check_links(graph: Dict[str, Any]) -> None:
    dangling = [(key, name, value) for key, node in graph.items() for name, value in node["inputs"].items()
                if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] not in graph]
    if dangling:
        raise RuntimeError(f"The shareable graph has dangling links: {dangling}")


# --------------------------------------------------------------------------------------------------------------------
# 3. Node definitions
# --------------------------------------------------------------------------------------------------------------------

def load_object_info(path: Optional[str], server: str) -> Dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    with urllib.request.urlopen(server.rstrip("/") + "/object_info", timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


_NODE_FOLDER_MODULE = None


def load_node_folder() -> Any:
    """``MiniMaxH3LongScene/`` as a package, without importing the rest of this pack."""
    global _NODE_FOLDER_MODULE
    if _NODE_FOLDER_MODULE is None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "vrgdg_cnp_minimax_h3_long_scene", NODE_FOLDER / "__init__.py",
            submodule_search_locations=[str(NODE_FOLDER)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _NODE_FOLDER_MODULE = module
    return _NODE_FOLDER_MODULE


def _class_info(cls: Any) -> Dict[str, Any]:
    spec = cls.INPUT_TYPES()
    return {
        "input": {section: spec.get(section, {}) for section in ("required", "optional")},
        "input_order": {section: list(spec.get(section, {})) for section in ("required", "optional")},
        "output": list(cls.RETURN_TYPES),
        "output_name": list(getattr(cls, "RETURN_NAMES", cls.RETURN_TYPES)),
    }


def node_info(info: Dict[str, Any], class_type: str) -> Dict[str, Any]:
    own = load_node_folder().NODE_CLASS_MAPPINGS.get(class_type)
    if own is not None:
        return _class_info(own)
    if class_type in info:
        return info[class_type]
    builder = getattr(importlib.import_module(ROOT.name), "NODE_CLASS_MAPPINGS", {}).get(class_type)
    if builder is not None:
        return _class_info(builder)
    raise RuntimeError(f"{class_type} is not installed in the ComfyUI the definitions came from.")


# --------------------------------------------------------------------------------------------------------------------
# 4. Canvas workflow
# --------------------------------------------------------------------------------------------------------------------

_WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}


def _is_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def _spec_parts(spec: Any) -> Tuple[Any, Dict[str, Any]]:
    kind = spec[0] if isinstance(spec, (list, tuple)) and spec else spec
    options = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 and isinstance(spec[1], dict) else {}
    return kind, options


def _default(kind: Any, options: Dict[str, Any]) -> Any:
    if "default" in options:
        return options["default"]
    if isinstance(kind, list):
        return kind[0] if kind else ""
    if kind == "COMBO":
        return (options.get("options") or [""])[0]
    return {"INT": 0, "FLOAT": 0.0, "BOOLEAN": False}.get(kind, "")


class CanvasBuilder:
    """Collects canvas nodes and links."""

    def __init__(self, info: Dict[str, Any]) -> None:
        self.info = info
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.links: List[List[Any]] = []

    def add_api_node(self, node_id: str, api_node: Dict[str, Any]) -> None:
        class_type = api_node["class_type"]
        spec = node_info(self.info, class_type)
        api_inputs = api_node["inputs"]
        inputs: List[Dict[str, Any]] = []
        widgets: List[Any] = []
        named_widgets: Dict[str, Any] = {}
        order = spec.get("input_order") or {section: list(spec["input"].get(section, {})) for section in ("required", "optional")}
        for section in ("required", "optional"):
            for name in order.get(section, []):
                kind, options = _spec_parts(spec["input"][section][name])
                if kind == "COMFY_AUTOGROW_V3":
                    template = options.get("template", {}).get("input", {})
                    slot_kind = next(iter({**template.get("required", {}), **template.get("optional", {})}.values()))[0]
                    for key, value in api_inputs.items():
                        if key.startswith(name + ".") and _is_link(value):
                            inputs.append({"name": key, "type": slot_kind, "link": None, "_source": value})
                    continue
                is_widget = (isinstance(kind, list) or kind in _WIDGET_TYPES) and not options.get("forceInput")
                value = api_inputs.get(name)
                if not is_widget:
                    socket_type = "COMBO" if isinstance(kind, list) else kind
                    inputs.append({"name": name, "type": socket_type, "link": None, "_source": value if _is_link(value) else None})
                    continue
                current = _default(kind, options) if value is None or _is_link(value) else value
                if _is_link(value):
                    socket_type = "COMBO" if isinstance(kind, list) else kind
                    inputs.append({"name": name, "type": socket_type, "link": None, "widget": {"name": name}, "_source": value})
                widgets.append(current)
                named_widgets[name] = current
                if options.get("control_after_generate"):
                    # Only seeds change between runs; sizes, steps and lengths stay as set.
                    widgets.append("randomize" if "seed" in name else "fixed")
                if options.get("image_upload"):
                    widgets.append("image")
        outputs = [{"name": out_name, "type": out_type, "links": []}
                   for out_type, out_name in zip(spec["output"], spec["output_name"])]
        if class_type == "VHS_VideoCombine":
            widget_values: Any = {**named_widgets, "pix_fmt": "yuv420p", "crf": api_inputs.get("crf", 19),
                                  "save_metadata": True, "trim_to_audio": False,
                                  "videopreview": {"hidden": False, "paused": False, "params": {}}}
        else:
            widget_values = widgets
        self.nodes[node_id] = {
            "id": int(node_id), "type": class_type, "pos": [0, 0], "size": [360, 120], "flags": {}, "order": 0,
            "mode": 0, "inputs": inputs, "outputs": outputs,
            "properties": {"Node name for S&R": class_type},
            "title": api_node.get("_meta", {}).get("title") or spec.get("display_name") or class_type,
            "widgets_values": widget_values,
        }

    def add_note(self, node_id: str, title: str, text: str) -> None:
        self.nodes[node_id] = {
            "id": int(node_id), "type": NOTE_TYPE, "pos": [0, 0], "size": [360, 200], "flags": {}, "order": 0,
            "mode": 0, "inputs": [], "outputs": [], "properties": {}, "title": title, "widgets_values": [text],
            "color": "#432", "bgcolor": "#653",
        }

    def connect(self) -> None:
        link_id = 0
        for node in self.nodes.values():
            for slot, entry in enumerate(node["inputs"]):
                source = entry.pop("_source", None)
                if not source:
                    continue
                origin = self.nodes[source[0]]
                link_id += 1
                origin["outputs"][source[1]]["links"].append(link_id)
                entry["link"] = link_id
                self.links.append([link_id, int(source[0]), source[1], node["id"], slot, entry["type"]])
        # A ComfyUI "order" is the run order: a node comes after everything it reads.
        incoming = {key: {str(link[1]) for link in self.links if str(link[3]) == key} for key in self.nodes}
        placed: List[str] = []
        while len(placed) < len(self.nodes):
            ready = sorted((key for key in self.nodes if key not in placed and incoming[key] <= set(placed)), key=int)
            if not ready:
                raise RuntimeError("The workflow has a cycle.")
            placed.extend(ready)
        for position, key in enumerate(placed):
            self.nodes[key]["order"] = position


def _height(node: Dict[str, Any]) -> int:
    if node["type"] == NOTE_TYPE:
        return max(160, 22 * (node["widgets_values"][0].count("\n") + 2) + 40)
    if node["type"] == "PrimitiveStringMultiline":
        return 760
    if node["type"] == "LoadImage":
        return 360
    if node["type"] == "VHS_VideoCombine":
        return 560
    if node["type"] == "PreviewAny":
        return 220
    widgets = len(node["widgets_values"]) if isinstance(node["widgets_values"], list) else len(node["widgets_values"])
    sockets = max(len(node["inputs"]), len(node["outputs"]))
    return 46 + 24 * sockets + 26 * widgets


# Groups left to right. Each group is a list of columns, each column a list of canvas node ids (n* = notes).
LAYOUT: List[Tuple[str, List[List[str]]]] = [
    ("START HERE", [["n900"]]),
    ("1 · MODELS", [["n901", "141", "128"], ["119", "120", "188"]]),
    ("2 · DMAD LORAS + LONG-SCENE MODEL PATCHES", [["n902", "9201", "9202", "9401"], ["207", "9203"]]),
    ("3 · YOUR INPUTS", [["n903", "301", "302"], ["171", "132", "115", "184", "185"], ["138"]]),
    ("4 · CONDITIONING + AUDIO LOCK", [["n904", "186", "187", "131"], ["136", "172"], ["9500", "9501"]]),
    ("5 · PASS 1 · DMAD 4 STEPS (LOW RES)", [["n905", "129", "123", "124"], ["126", "125"]]),
    ("6 · PASS 2 · REFINE IN WINDOWS (LONG SCENES)", [["n906", "210", "190", "191"], ["192", "9502", "303"]]),
    ("7 · DECODE + SAVE", [["n907", "122", "304"], ["183", "142"]]),
]

COLUMN_WIDTH = 380
COLUMN_GAP = 30
GROUP_GAP = 80
TOP = 60
TITLE_SPACE = 50
PAD = 20


def lay_out(canvas: CanvasBuilder) -> List[Dict[str, Any]]:
    groups = []
    x = 0
    placed = set()
    for index, (title, columns) in enumerate(LAYOUT):
        bottom = 0
        width = COLUMN_WIDTH if title == "START HERE" else COLUMN_WIDTH
        if title == "START HERE":
            width = 560
        for column, ids in enumerate(columns):
            y = TOP + TITLE_SPACE
            for node_id in ids:
                node = canvas.nodes[node_id.lstrip("n")]
                node["pos"] = [x + PAD + column * (width + COLUMN_GAP), y]
                node["size"] = [width, _height(node)]
                y += node["size"][1] + 40
                placed.add(node_id.lstrip("n"))
            bottom = max(bottom, y)
        group_width = len(columns) * width + (len(columns) - 1) * COLUMN_GAP + 2 * PAD
        groups.append({
            "id": index + 1, "title": title, "bounding": [x, TOP, group_width, bottom - TOP],
            "color": GROUP_COLORS[index % len(GROUP_COLORS)], "font_size": 24, "flags": {},
        })
        x += group_width + GROUP_GAP
    missing = sorted(set(canvas.nodes) - placed, key=int)
    if missing:
        raise RuntimeError(f"Nodes with no place in the layout: {[canvas.nodes[key]['type'] for key in missing]}")
    return groups


# --------------------------------------------------------------------------------------------------------------------
# 5. Notes
# --------------------------------------------------------------------------------------------------------------------

def notes(payload: Dict[str, Any], api: Dict[str, Any]) -> Dict[str, Tuple[str, str]]:
    chunk = api[_single(api, "VRGDG_MiniMaxH3ChunkedPass2")]["inputs"]
    lora_rows = "\n".join(f"- `{name}` -> `models/{folder}`" for name, folder in (
        (payload.get("diffusion_model_name") or "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "diffusion_models"),
        (payload.get("clip_name") or "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "text_encoders"),
        ("minimax_h3_video_vae_fp16.safetensors", "vae"),
        ("minimax_h3_audio_vae_fp32.safetensors", "vae"),
        ("minimax_h3_latent_upscaler_3d_bf16.safetensors", "latent_upscale_models"),
        ("dmad_minimax_h3_4step_full_critic_comfyui.safetensors", "loras"),
        ("minimax_h3_open_regenerate_2k_refiner_rank_16_bf16.safetensors", "loras"),
    ))
    return {
        "900": ("READ ME - MiniMax H3 DMAD + Long Scenes", (
            "# MiniMax H3 · DMAD + Long Scenes (2 Pass)\n\n"
            "The same graph the **VRGDG Video Builder** renders when a scene uses **2 Pass**, **DMAD** and "
            "**Long Scenes** (pass 2 in batches). It is generated from the Builder's own code, with the Builder's "
            "default values.\n\n"
            "**How it works**\n"
            "1. **Pass 1** renders the whole scene at low resolution in 4 DMAD steps.\n"
            "2. **Pass 2** upscales and refines it in short overlapping windows "
            f"({chunk['chunk_seconds']:g} s windows, {chunk['overlap_seconds']:g} s locked overlap). Only one window is on "
            "the GPU at a time, so long scenes (up to ~15 s) fit in memory.\n"
            "3. **Audio**: one switch, `built_in_audio` on the **AUDIO** node in group 3.\n"
            "   - **Off (my song)**: your song is locked in, and H3 makes only the picture.\n"
            "   - **On (built-in audio)**: H3 makes the singing and sound itself, and no song file is needed.\n\n"
            "**Use it**\n"
            "1. Load your reference pictures in group **3**.\n"
            "2. Choose the audio mode. For your song, set `audio_file` and the scene start (`seek_seconds`).\n"
            "3. Set **Duration**.\n"
            "4. Write the prompt for that mode (see the note in group 3). Pass 2 gets a copy without the lyric text "
            "and times automatically.\n"
            "5. Queue.\n\n"
            "**Node packs needed**\n"
            "- ComfyUI with the MiniMax H3 nodes (recent ComfyUI)\n"
            "- **VRGDG Custom Node Pack**: pass 2 prompt and the audio switch\n"
            "- **comfyui-vrgamedevgirl** (Video Builder): VRGDG H3 Chunked Pass 2 and the latent upscaler loader\n"
            "- Comfyui_Minimax_h3_latent_Upscaler: the learned latent upscaler itself\n"
            "- ComfyUI-KJNodes\n"
            "- ComfyUI-VideoHelperSuite\n\n"
            "**Model files**\n" + lora_rows + "\n\n"
            "DMAD LoRA: huggingface.co/ZhengmingYu/DMAD (folder `minimax_h3`)\n"
            "Refiner LoRA: huggingface.co/Kijai/MiniMax-H3-experimental (folder `loras`)\n"
            "In the Video Builder: Models > DMAD Models installs both."
        )),
        "901": ("Note - Models", (
            "**Models**\n\n"
            "The H3 Reference-to-Video model, its text encoder, both VAEs and the learned latent upscaler.\n\n"
            "`sage_attention` auto and fp16 accumulation are the Builder defaults. Set them to off if your setup "
            "does not support them."
        )),
        "902": ("Note - DMAD LoRAs", (
            "**DMAD**\n\n"
            "- **Pass 1** uses the **DMAD 4-step LoRA** (strength 1) and a **sigma shift of 12 video / 2 audio**.\n"
            "- **Pass 2** uses the **Refiner LoRA** at **0.7**.\n\n"
            "**Chunk FeedForward** (KJNodes) is on for both passes. The Builder turns it on for every scene over "
            "8 s, so long scenes stay inside memory.\n\n"
            "Keep the DMAD LoRA on pass 1 only: its 4-step sampler does not work without it."
        )),
        "903": ("Note - Your inputs", (
            "**Your inputs**\n\n"
            "- **References**: `<Picture 1>` and `<Picture 2>` in the prompt are these images, in order. To add more, "
            "drag another Load Image into the next `ref_image` slot of **both** Reference to Video nodes in "
            "group 4. With more than 5 pictures, set `ref_image_size` to `match` on both (the Builder does this).\n"
            "- **Audio switch** (`built_in_audio`):\n"
            "  - **Off, my song**: `audio_file` is the full path to your song, or a file name in `ComfyUI/input`. "
            "`seek_seconds` is where the scene starts in the song; the length comes from **Duration**. The prompt "
            "calls the song `<Audio 1>`.\n"
            "  - **On, built-in audio**: H3 sings and makes the sound itself, and `audio_file` is ignored. In the "
            "prompt, do not mention `<Audio 1>`. Describe the voice once, and put the words to sing in the `<d>` "
            "cues: `sings from 1.0 s to 4.4 s, <d>[English, warm singing] the words</d>`.\n"
            "- **Duration**: the scene length in seconds (H3 renders up to ~15 s). It is rounded up to H3's frame "
            "grid, so the video can be a few frames longer than the audio. The Builder trims that off; trim it in "
            "your editor.\n"
            "- **Width / Height**: the final video size. Pass 1 renders at this size divided by the **Upscale "
            "Scale**.\n"
            "- **Prompt**: the Builder's six-section H3 format works best. Lyric cues are `from 1.0 s to 4.4 s, "
            "<d>[tags] words</d>`, with times counted from the scene start."
        )),
        "904": ("Note - Conditioning", (
            "**Conditioning**\n\n"
            "- The first Reference to Video node reads your prompt for pass 1.\n"
            "- **Pass 2 Prompt (No Lyric Times)** removes the lyric cues, sung words and shot times. Each pass 2 "
            "window starts its own clock at 0, so whole-scene times would mislead it. The second Reference to "
            "Video node conditions the windows with that text.\n"
            "- **Lock song** puts your song into the latent, so H3 generates the picture only and the singing stays "
            "in sync. With built-in audio it passes the latent through, and H3 makes the sound too.\n"
            "- With built-in audio, the Reference to Video nodes get no reference audio. The AUDIO node sends "
            "nothing to `ref_audio_0`, which is the same as the Builder's built-in graph."
        )),
        "905": ("Note - Pass 1", (
            "**Pass 1 · DMAD**\n\n"
            "`lcm` / `simple` / **4 steps** / denoise 1, at low resolution. These are the DMAD defaults; there is no "
            "need to raise the steps.\n\n"
            "Change the **seed** for a different take."
        )),
        "906": ("Note - Pass 2 in windows", (
            "**Pass 2 · in windows**\n\n"
            "`res_multistep` / `simple` / **3 steps** / denoise **0.2** (DMAD defaults).\n\n"
            "**VRGDG H3 Chunked Pass 2** does the learned upscale and the refinement one window at a time, then "
            "joins them. The Builder's values:\n"
            f"- `chunk_seconds` {chunk['chunk_seconds']:g}: window length\n"
            f"- `overlap_seconds` {chunk['overlap_seconds']:g}, `overlap_mode` {chunk['overlap_mode']}: each window "
            "keeps the end of the one before it fixed, so there are no seams\n"
            f"- `tail_trim_seconds` {chunk['tail_trim_seconds']:g}: each window's last part is redone by the next one\n"
            f"- `upscale` {chunk['upscale']}: the upscaler also works one window at a time\n\n"
            "The Builder uses windows only for clips longer than 8 s. For a short scene this node still works; "
            "it just makes fewer windows.\n\n"
            "The **Window report** shows the windows that ran."
        )),
        "907": ("Note - Decode and save", (
            "**Decode + save**\n\n"
            "The refined latent is decoded, resized to your exact width x height and saved as an MP4 in "
            "`output/`.\n\n"
            "**Video soundtrack** is your song, or with built-in audio the sound H3 made in pass 1 (pass 2 keeps "
            "that audio exactly)."
        )),
    }


# --------------------------------------------------------------------------------------------------------------------
# 6. Main
# --------------------------------------------------------------------------------------------------------------------

def export(info: Dict[str, Any], output: Path = OUTPUT) -> Dict[str, Any]:
    api, payload = build_builder_graph()
    graph = shareable_graph(api)
    canvas = CanvasBuilder(info)
    for node_id, node in sorted(graph.items(), key=lambda item: int(item[0])):
        canvas.add_api_node(node_id, node)
    for node_id, (title, text) in notes(payload, api).items():
        canvas.add_note(node_id, title, text)
    canvas.connect()
    groups = lay_out(canvas)
    nodes = sorted(canvas.nodes.values(), key=lambda node: node["order"])
    workflow = {
        "last_node_id": max(node["id"] for node in nodes),
        "last_link_id": len(canvas.links),
        "nodes": nodes,
        "links": canvas.links,
        "groups": groups,
        "config": {},
        "extra": {
            "ds": {"scale": 0.55, "offset": [40, 40]},
            "vrgdg": {
                "generated_by": "optional_nodes/ltx_minimax_tools/scripts/export_dmad_long_scene_workflow.py",
                "builder_settings": {"render_pass": "two_pass", "use_dmad": True, "pass2_chunking": "auto",
                                     "video_mode": "reference_to_video"},
            },
        },
        "version": 0.4,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, output)
    return workflow


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--object-info", help="A saved /object_info JSON file instead of asking a running ComfyUI.")
    parser.add_argument("--server", default="http://127.0.0.1:8188", help="Running ComfyUI to read /object_info from.")
    parser.add_argument("--output", default=str(OUTPUT), help="Where to write the workflow.")
    parser.add_argument("--builder-pack", default=str(DEFAULT_BUILDER_PACK), help="The comfyui-vrgamedevgirl folder.")
    args = parser.parse_args(argv)
    use_builder_pack(Path(args.builder_pack))
    workflow = export(load_object_info(args.object_info, args.server), Path(args.output))
    print(f"{LOG_PREFIX} Wrote {args.output} ({len(workflow['nodes'])} nodes, {len(workflow['links'])} links, "
          f"{len(workflow['groups'])} groups).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
