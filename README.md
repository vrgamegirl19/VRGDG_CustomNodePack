# VRGDG Custom Node Pack

Private development pack for ComfyUI. Not ready for public release.

Contains the eight `optional_nodes` packs copied from
[`comfyui-vrgamedevgirl`, branch `Beta2.0`](https://github.com/vrgamegirl19/comfyui-vrgamedevgirl/tree/Beta2.0/optional_nodes)
at commit `99c01f654b16f65ae6a73f636563d208934c20c7`.
The source repository and its branches are unchanged.

## Included packs

| Pack | Nodes | Tools |
| --- | ---: | --- |
| `face_fix` | 20 | Face repair, face crops, video enhancement, image paste-back |
| `general_utilities` | 70 | Text/JSON, switches, grain, sharpening, color matching, LUTs, image/video comparison, audio splitting |
| `llm_nodes` | 6 | Qwen, VLM, GGUF, local LLM, llama.cpp diagnostics |
| `long_video` | 12 | Overlap meta-batches, long-video loading, LongShot directors |
| `lora_training` | 14 | LTX, Krea and Z-Image LoRA training, installers, dataset creation |
| `ltx_minimax_tools` | 16 | LTX guides and looping, sigma presets, MiniMax chunks, still images, continuation trimming |
| `music_audio` | 19 | YuE2, SheetSage2, MiniMax Music 3, VoxCPM2, audio loading/saving |
| `ui_tools` | 10 | Video Editor, Prompt Creator, Start Image Storyboard, Node Canvas |

Node identifiers are preserved for existing workflows. Examples remain in each
pack's `workflows/` folder. Model weights are not included, apart from the face
detection assets already bundled with the source pack.

## Install the complete pack

Use a GitHub account with access to this private repository. From
`ComfyUI/custom_nodes`, run:

```sh
git clone https://github.com/vrgamegirl19/VRGDG_CustomNodePack.git
```

Install dependencies with the Python environment that runs ComfyUI:

```sh
python -m pip install -r VRGDG_CustomNodePack/requirements.txt
```

For Windows portable, run this from `ComfyUI_windows_portable` instead:

```powershell
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\VRGDG_CustomNodePack\requirements.txt
```

Restart ComfyUI and refresh the browser. The root `__init__.py` registers all
eight packs; `web/` serves their frontend extensions. An INI file is not required
for ComfyUI node registration.

If a pack has a missing import dependency, the other packs still load. Read the
startup warning and install the dependency using ComfyUI's Python. Installing
`llama-cpp-python` may require a compatible wheel or local build tools.

## Additional setup

- Install [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo)
  for the LTX looping sampler in `ltx_minimax_tools`.
- Install [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)
  for long-video loading and workflows using VHS nodes.
- Training nodes need their external training tools and model files configured
  through the existing installer/settings nodes.
- See [YuE2 setup](optional_nodes/music_audio/Yue2/README.md) for its separate
  generation and transcription runtimes.
- Browser automation has separate setup in
  [flow_automation/README.md](optional_nodes/ui_tools/flow_automation/README.md).
- Builder-integrated UI actions and example workflows can also require nodes
  and routes from `comfyui-vrgamedevgirl` or other packs named in the workflow.
- Put your `.cube` LUT files in `optional_nodes/general_utilities/LUTS/`.

Avoid installing a second copy of these optional packs alongside the complete
pack: duplicate node identifiers and frontend extensions can conflict. The
reduced `Beta2.0` source pack excludes these optional nodes; older installations
that still load them should use only one copy.

## Install individual packs

To use only selected packs, keep this repository outside `custom_nodes` and copy
the chosen folders into `ComfyUI/custom_nodes`. For example, in PowerShell:

```powershell
Copy-Item -Recurse .\VRGDG_CustomNodePack\optional_nodes\face_fix .\ComfyUI\custom_nodes\vrgdg_face_fix
python -m pip install -r .\ComfyUI\custom_nodes\vrgdg_face_fix\requirements.txt
```

Use ComfyUI's Python, then restart. Each folder retains its own registration,
frontend assets, requirements and workflows.

## Development notes

The imported Python code stays under `optional_nodes/`. Root `web/` contains
deployment copies of each pack's frontend assets with script import paths
adjusted for ComfyUI's extension URLs. Keep those copies in sync when editing
frontend files. The LoRA pack includes the two internal workflow templates its
code references. The LTX extension lookup uses ComfyUI's configured custom-node
directories so it works from the nested pack layout.

Validation covers Python syntax, the included unit tests, node registration and
frontend import paths. Model generation and training require separate runtime
testing with the relevant models and tools.

## Licensing and visibility

Imported code and documentation retain the source terms in
[`optional_nodes/LICENSE`](optional_nodes/LICENSE). Frontend deployment copies
retain those terms in [`web/LICENSE`](web/LICENSE). The repository's existing
Apache 2.0 [`LICENSE`](LICENSE) is retained for the new repository scaffolding;
it does not replace the imported code's license or third-party asset licenses.

This repository must remain private during development. There are no release,
registry publication or deployment workflows in this pack.
