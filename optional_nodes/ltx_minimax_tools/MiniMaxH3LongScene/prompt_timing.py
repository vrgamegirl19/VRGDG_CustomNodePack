"""Remove lyric cues, sung words and shot times from a MiniMax H3 prompt (pure Python).

Copied from ``strip_prompt_timing`` in comfyui-vrgamedevgirl ``runner/minimax_chunked_pass2.py``, which makes the
Video Builder's pass 2 prompt for Long Scenes. Keep the two in step.
"""

from __future__ import annotations

import re
from typing import List, Optional

_CUE_WITH_TEXT = re.compile(r"[ \t]*from \d+(?:\.\d+)? s to \d+(?:\.\d+)? s,?[ \t]*<d>.*?</d>", re.DOTALL)
_DIALOGUE = re.compile(r"[ \t]*<d>.*?</d>", re.DOTALL)
_CUE_TIME = re.compile(r"[ \t]*from \d+(?:\.\d+)? s to \d+(?:\.\d+)? s")
_SHOT_TIME = re.compile(r"^(\[Shot \d+\][ \t]*)At \d\d:\d\d(?:\.\d+)?,[ \t]*(\S)", re.MULTILINE)
_SHOT_PARAGRAPH = re.compile(r"^\[Shot (\d+)\][ \t]*(.*)$", re.DOTALL)
_SECTION_LINE = re.compile(r"^[a-z_]{4,}:[ \t]*$", re.MULTILINE)


def _merge_repeated_shots(text: str) -> str:
    """Drop a ``[Shot n]`` paragraph that repeats the one before it word for word, and renumber what is left.

    Shots in one unbroken take often differ only by their lyric and start time. Once those are removed they read the
    same, and a window would be told the same shot six times. Only directly repeated shots go; a shot that returns
    after a different one stays, and a prompt with no repeats comes back exactly as it was.
    """
    parts = re.split(r"(\n[ \t]*\n)", text)
    kept: List[str] = []
    previous: Optional[str] = None
    number = dropped = 0
    for position in range(0, len(parts), 2):
        paragraph = parts[position]
        separator = parts[position - 1] if position else ""
        match = _SHOT_PARAGRAPH.match(paragraph)
        if match and not _SECTION_LINE.search(paragraph):
            body = match.group(2).strip()
            if body == previous:
                dropped += 1
                continue
            previous = body
            number += 1
            if dropped:
                paragraph = f"[Shot {number}] {body}"
        else:
            previous = None
        kept.append(separator + paragraph)
    if not dropped:
        return text
    return "".join(kept).rstrip() + text[len(text.rstrip()):]


def strip_prompt_timing(text: str) -> str:
    """The prompt with its lyric cues, dialogue text and shot start times removed.

    ``sings in sync with the vocals in <Audio 1> from 1.0 s to 4.4 s, <d>[tag] words</d>, delivered softly`` becomes
    ``sings in sync with the vocals in <Audio 1>, delivered softly``. A ``[Shot 2] At 00:04.600, continuing ...``
    becomes ``[Shot 2] Continuing ...``, and shots that then repeat the one before them are merged into it.
    Everything else, including the look, the references and the shot descriptions, is kept.
    """
    result = _CUE_WITH_TEXT.sub("", text)
    result = _DIALOGUE.sub("", result)
    result = _CUE_TIME.sub("", result)
    result = _SHOT_TIME.sub(lambda match: match.group(1) + match.group(2).upper(), result)
    result = re.sub(r"[ \t]+,", ",", result)
    result = re.sub(r"(?<=\S)[ \t]{2,}", " ", result)
    return _merge_repeated_shots(result)
