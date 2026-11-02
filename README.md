# VRGDG Custom Node Pack

**167 ComfyUI nodes for image and video processing, face repair, audio, local LLMs, LoRA training, and creative workflow tools.**

Build face-repair workflows, process long videos, prepare music and speech, create prompts, train LoRAs, and add practical image, text, JSON, and batch utilities to your ComfyUI workflows.

## What's included

| Node group | Nodes | Features |
| --- | ---: | --- |
| Face Fix & Video Enhance | 20 | Face detection and tracking, repair crops, enhancement anchors, video restoration, and image paste-back |
| General Utilities | 70 | Text and JSON tools, image switches, film grain, sharpening, color matching, LUTs, image/video comparison, and audio splitting |
| Local LLMs | 6 | Qwen prompt generation, VLM and GGUF tools, local LLM connections, and llama.cpp diagnostics |
| Long Video | 12 | Overlapping video batches, audio windows, long-video loading, and LongShot planning tools |
| LoRA Training | 14 | LTX, Krea, and Z-Image training tools, dataset creation, installers, and preview grids |
| LTX & MiniMax H3 | 16 | Guidance and sigma controls, first/last-frame guides, looping, ingredient grids, connected chunks, still images, and continuation trimming |
| Music & Audio | 19 | YuE2, SheetSage2, MiniMax Music 3 helpers, VoxCPM2 speech, and audio loading/saving |
| Workflow UIs | 10 | Video Editor, Prompt Creator, Start Image Storyboard, and Node Canvas prototype |

## Installation

### ComfyUI Manager

1. Open **ComfyUI Manager** and search for **VRGDG Custom Node Pack** or `vrgdg-customnodepack`.
2. Install the pack and its dependencies.
3. Restart ComfyUI and refresh the browser with **Ctrl+F5**.

If the pack is not listed yet, use the manual installation below.

### Manual installation

From your `ComfyUI/custom_nodes` directory, run:

```sh
git clone https://github.com/vrgamegirl19/VRGDG_CustomNodePack.git
python -m pip install -r VRGDG_CustomNodePack/requirements.txt
```

Use the Python environment that runs ComfyUI, then restart ComfyUI and refresh your browser.

### Windows portable

Run these commands from your `ComfyUI_windows_portable` directory:

```powershell
git -C .\ComfyUI\custom_nodes clone https://github.com/vrgamegirl19/VRGDG_CustomNodePack.git
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\VRGDG_CustomNodePack\requirements.txt
```

Restart ComfyUI and refresh your browser with **Ctrl+F5**.

## Getting started

Right-click the ComfyUI canvas and search for the node you want to use. Node categories include **VRGDG** and **VRGameDevGirl**.

Start with one of the included workflows:

- [Face Fix](optional_nodes/face_fix/workflows/VRGDG_FaceFix_Workflow.json)
- [Match Grain — Image](optional_nodes/general_utilities/workflows/match%20grain/Match_Grain_Image.json)
- [Match Grain — Video](optional_nodes/general_utilities/workflows/match%20grain/Match_Grain_Video.json)
- [MiniMax Music 3 Advanced Tuning](optional_nodes/music_audio/workflows/MiniMax_Music3_Advanced_Tuning_VRGDG.json)
- [VoxCPM2 Voice Clone / TTS](optional_nodes/music_audio/workflows/VoxCPM2/VRGDG_VoxCPM_TTS.json)
- [YuE2 Starter](optional_nodes/music_audio/workflows/Yue2/VRGDG_YuE2_Starter.json)
- [LoRA Training Workflows](optional_nodes/lora_training/workflows/Lora_Training/UpdatedWorkflows/)

Download a workflow JSON and drag it onto the ComfyUI canvas. Install any additional nodes named by that workflow and select your local model files before running it.

## Models and additional setup

Each tool has its own model and runtime requirements. Generation model weights are separate downloads; the pack includes the bundled face-detection assets.

- **LTX looping:** requires [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo).
- **Long-video loading and VHS workflows:** require [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite).
- **Local LLMs:** configure a supported model or local server. GGUF tools require `llama-cpp-python`; installation may need a compatible wheel or local build tools.
- **LoRA training:** configure the external training tools, datasets, and model paths using the relevant installer and settings nodes.
- **YuE2 and SheetSage2:** follow the [setup guide](optional_nodes/music_audio/Yue2/README.md) for their generation and transcription runtimes.
- **Browser automation:** follow the [browser automation guide](optional_nodes/ui_tools/flow_automation/README.md).
- **LUTs:** place your `.cube` files in `optional_nodes/general_utilities/LUTS/`.
- **Builder integrations:** some UI actions and workflows also use nodes or routes from [VRGameDevGirl's AI Video Builder](https://github.com/vrgamegirl19/comfyui-vrgamedevgirl).

## Updating

From the installed `VRGDG_CustomNodePack` folder, run:

```sh
git pull
python -m pip install -r requirements.txt
```

Use ComfyUI's Python environment. For Windows portable, run these commands from `ComfyUI_windows_portable`:

```powershell
git -C .\ComfyUI\custom_nodes\VRGDG_CustomNodePack pull
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\VRGDG_CustomNodePack\requirements.txt
```

Restart ComfyUI and refresh the browser after updating.

## Troubleshooting

- **Nodes are missing:** check the ComfyUI startup log for the pack name and missing dependencies. Install requirements using the same Python that starts ComfyUI.
- **UI buttons or panels are missing:** restart ComfyUI, then refresh with **Ctrl+F5**.
- **A workflow reports missing nodes:** install the additional node packs required by that workflow.
- **Duplicate nodes or extensions:** keep one installed copy of each pack. Older versions of `comfyui-vrgamedevgirl` may already include these node identifiers.
- **Generation or training cannot start:** check the selected model files, external runtime paths, and the setup instructions for that tool.

For help or bug reports, [open an issue](https://github.com/vrgamegirl19/VRGDG_CustomNodePack/issues) with the affected node name, the error traceback, your ComfyUI and Python versions, and a minimal workflow when possible. Remove API keys and other secrets before sharing logs or workflows.

## License

The node code and associated documentation retain the [VRGameDevGirl Community and Commercial License](optional_nodes/LICENSE). Frontend assets retain the terms in [web/LICENSE](web/LICENSE). Repository scaffolding is covered by the root [Apache 2.0 license](LICENSE). Third-party components and model weights retain their respective licenses.
