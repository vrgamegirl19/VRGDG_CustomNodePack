"""VRGDG H3 Pass 2 Prompt (No Lyric Times): the prompt the windows of VRGDG H3 Chunked Pass 2 read."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .prompt_timing import strip_prompt_timing


class VRGDG_MiniMaxH3Pass2PromptNoTiming:
    """The scene prompt with its lyric text and times removed, for the windows of the chunked second pass."""

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {"required": {
            "prompt": ("STRING", {
                "multiline": True, "forceInput": True,
                "tooltip": "The same prompt pass 1 reads, with its lyric cues and shot times.",
            }),
        }}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("pass2_prompt",)
    FUNCTION = "strip"
    CATEGORY = "VRGDG/MiniMax H3"
    DESCRIPTION = (
        "Removes lyric cues, sung words and shot start times from a MiniMax H3 prompt and merges shots that then "
        "repeat. Each window of VRGDG H3 Chunked Pass 2 starts its clock at 0, so whole-scene times would mislead "
        "it. The Video Builder makes its pass 2 prompt the same way."
    )

    def strip(self, prompt: str) -> Tuple[str]:
        return (strip_prompt_timing(prompt or ""),)


NODE_CLASS_MAPPINGS = {"VRGDG_MiniMaxH3Pass2PromptNoTiming": VRGDG_MiniMaxH3Pass2PromptNoTiming}
NODE_DISPLAY_NAME_MAPPINGS = {"VRGDG_MiniMaxH3Pass2PromptNoTiming": "VRGDG H3 Pass 2 Prompt (No Lyric Times)"}
