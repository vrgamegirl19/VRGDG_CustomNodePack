# Changelog

## Unreleased

- Add the VRGDG MiniMax node: a one-button studio for MiniMax H3 text, image and reference to video with two-pass batched refinement, size and VRAM window presets, advanced pass 1 / pass 2 settings and a setup check with download links.
- Add H3 Chunked Pass 2 - Standalone and H3 Unload Models Before Decode, so the studio's workflows run without the Video Builder.
- Add the MiniMax H3 DMAD + Long Scenes (2 Pass) workflow to `ltx_minimax_tools/workflows/`, generated from the Video Builder's own graph by `ltx_minimax_tools/scripts/export_dmad_long_scene_workflow.py`.
- Add `ltx_minimax_tools/MiniMaxH3LongScene/`: VRGDG H3 Pass 2 Prompt (No Lyric Times) and the song / built-in audio switch (Audio Source, Lock Song, Video Soundtrack).
- Copy all eight optional node packs from `Beta2.0` commit `99c01f6`.
- Add a root ComfyUI entry point, combined requirements and frontend assets.
- Resolve LTXVideo through ComfyUI's configured custom-node directories.
- Include the two workflow templates used by the LoRA training pack.
- Document installation, dependencies and retained source licensing.
