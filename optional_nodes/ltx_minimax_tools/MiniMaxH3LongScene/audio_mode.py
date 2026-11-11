"""VRGDG H3 audio switch. One switch for MiniMax H3's two audio modes in a canvas workflow: your song, or H3's built-in audio.

The Video Builder (comfyui-vrgamedevgirl) builds a different graph for each mode (``_use_minimax_h3_native_audio`` in
its ``runner/minimax_workflows.py``). With your song, the song is ``<Audio 1>`` on the conditioning, it is locked into
the pass 1 latent, and it is the video's soundtrack. With built-in audio there is no reference audio and no lock,
and the soundtrack is the audio H3 generated in pass 1. These three nodes make both graphs one workflow:

- ``VRGDG_MiniMaxH3AudioSource`` loads the song, or gives nothing when built-in audio is on. MiniMax H3 Reference
  to Video skips a reference audio that is nothing.
- ``VRGDG_MiniMaxH3AudioLockSwitch`` locks the song into the latent, or passes the latent through.
- ``VRGDG_MiniMaxH3VideoSoundtrack`` gives the song, or decodes the latent's audio.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

import torch

LOG_PREFIX = "[VRGDG H3 Audio]"
BUILT_IN_TOOLTIP = "Off: your song drives the video. On: H3 makes the singing and sound itself (built-in audio)."


def crop_waveform(waveform: torch.Tensor, sample_rate: int, seek_seconds: float, duration: float) -> torch.Tensor:
    """``waveform`` [channels, samples] from ``seek_seconds`` for ``duration`` seconds (0 = to the end)."""
    start = max(0, int(round(float(seek_seconds or 0) * sample_rate)))
    if start >= waveform.shape[-1]:
        raise ValueError(f"The song is shorter than the start time ({seek_seconds:g} s).")
    end = waveform.shape[-1] if not duration or duration <= 0 else min(
        waveform.shape[-1], start + int(round(float(duration) * sample_rate)))
    return waveform[..., start:end]


def resolve_audio_path(audio_file: str) -> str:
    """A full path, or a file name in ComfyUI's input folder."""
    text = str(audio_file or "").strip().strip('"')
    if not text:
        raise ValueError("Set audio_file to your song, or turn built_in_audio on.")
    if os.path.isabs(text):
        candidates = [text]
    else:
        import folder_paths

        candidates = [os.path.join(folder_paths.get_input_directory(), text), text]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    raise FileNotFoundError(f"Song not found: {text}")


def _built_in(value: Any) -> bool:
    return bool(value)


class VRGDG_MiniMaxH3AudioSource:
    """Your song for MiniMax H3, or nothing when H3 makes the audio."""

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {"required": {
            "built_in_audio": ("BOOLEAN", {
                "default": False, "label_on": "built-in audio (H3 sings)", "label_off": "my song",
                "tooltip": BUILT_IN_TOOLTIP,
            }),
            "audio_file": ("STRING", {
                "default": "", "tooltip": "Full path to the song, or a file name in ComfyUI/input. Not used with built-in audio.",
            }),
            "seek_seconds": ("FLOAT", {
                "default": 0.0, "min": 0.0, "max": 100000.0, "step": 0.01,
                "tooltip": "Where the scene starts in the song.",
            }),
            "duration": ("FLOAT", {
                "default": 0.0, "min": 0.0, "max": 100000.0, "step": 0.01,
                "tooltip": "Seconds of song to use (0 = to the end). Connect the scene Duration.",
            }),
        }}

    RETURN_TYPES = ("AUDIO", "BOOLEAN")
    RETURN_NAMES = ("song", "built_in_audio")
    FUNCTION = "load"
    CATEGORY = "VRGDG/MiniMax H3"
    DESCRIPTION = (
        "Loads the scene's part of your song for MiniMax H3, or gives nothing when built_in_audio is on. Connect "
        "song to ref_audio_0 of the Reference to Video nodes and built_in_audio to the Lock Song and Video "
        "Soundtrack nodes, so one switch changes the whole workflow."
    )

    def load(self, built_in_audio: bool, audio_file: str, seek_seconds: float, duration: float) -> Tuple[Any, bool]:
        if _built_in(built_in_audio):
            print(f"{LOG_PREFIX} Built-in audio: no song is used, H3 makes the sound.")
            return (None, True)
        from comfy_extras.nodes_audio import load as load_audio

        path = resolve_audio_path(audio_file)
        waveform, sample_rate = load_audio(path)
        waveform = crop_waveform(waveform, sample_rate, seek_seconds, duration)
        print(f"{LOG_PREFIX} Song: {os.path.basename(path)} from {float(seek_seconds):g} s, "
              f"{waveform.shape[-1] / sample_rate:.2f} s.")
        return ({"waveform": waveform.unsqueeze(0), "sample_rate": int(sample_rate)}, False)


class VRGDG_MiniMaxH3AudioLockSwitch:
    """Lock your song into the pass 1 latent, or leave the latent as it is for built-in audio."""

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {"required": {
            "av_latent": ("LATENT", {"tooltip": "Joint AV latent from MiniMax H3 Reference to Video."}),
            "audio_vae": ("VAE",),
            "built_in_audio": ("BOOLEAN", {"default": False, "forceInput": True, "tooltip": BUILT_IN_TOOLTIP}),
        }, "optional": {
            "song": ("AUDIO", {"tooltip": "From VRGDG H3 Audio Source."}),
        }}

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("pass1_latent",)
    FUNCTION = "apply"
    CATEGORY = "VRGDG/MiniMax H3"
    DESCRIPTION = (
        "With your song: the same lock as VRGDG MiniMax H3 Audio Drive, so H3 makes only the picture. With "
        "built-in audio: the latent passes through and H3 makes the sound too."
    )

    def apply(self, av_latent: Dict[str, Any], audio_vae: Any, built_in_audio: bool,
              song: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any]]:
        if _built_in(built_in_audio):
            return (av_latent,)
        if song is None:
            raise ValueError("Connect the song from VRGDG H3 Audio Source, or turn built_in_audio on.")
        from ..VRGDG_MiniMaxH3AudioDrive import VRGDG_MiniMaxH3AudioDrive

        return (VRGDG_MiniMaxH3AudioDrive().apply_audio_drive(av_latent, song, audio_vae)[0],)


class VRGDG_MiniMaxH3VideoSoundtrack:
    """The video's sound: your song, or the audio H3 generated."""

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Any]:
        return {"required": {
            "av_latent": ("LATENT", {
                "tooltip": "A joint AV latent after pass 1 (pass 1 or the refined pass 2; both keep pass 1's audio).",
            }),
            "audio_vae": ("VAE",),
            "built_in_audio": ("BOOLEAN", {"default": False, "forceInput": True, "tooltip": BUILT_IN_TOOLTIP}),
        }, "optional": {
            "song": ("AUDIO", {"tooltip": "From VRGDG H3 Audio Source."}),
        }}

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "pick"
    CATEGORY = "VRGDG/MiniMax H3"
    DESCRIPTION = (
        "With your song: the song, unchanged. With built-in audio: the audio H3 generated, decoded from the "
        "latent the same way the Video Builder does."
    )

    def pick(self, av_latent: Dict[str, Any], audio_vae: Any, built_in_audio: bool,
             song: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any]]:
        if not _built_in(built_in_audio):
            if song is None:
                raise ValueError("Connect the song from VRGDG H3 Audio Source, or turn built_in_audio on.")
            return (song,)
        from comfy_extras.nodes_lt_audio import LTXVAudioVAEDecode

        output = LTXVAudioVAEDecode.execute(av_latent, audio_vae)
        return (output.result[0],)


NODE_CLASS_MAPPINGS = {
    "VRGDG_MiniMaxH3AudioSource": VRGDG_MiniMaxH3AudioSource,
    "VRGDG_MiniMaxH3AudioLockSwitch": VRGDG_MiniMaxH3AudioLockSwitch,
    "VRGDG_MiniMaxH3VideoSoundtrack": VRGDG_MiniMaxH3VideoSoundtrack,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VRGDG_MiniMaxH3AudioSource": "VRGDG H3 Audio Source (Song or Built-in)",
    "VRGDG_MiniMaxH3AudioLockSwitch": "VRGDG H3 Lock Song (skipped for built-in audio)",
    "VRGDG_MiniMaxH3VideoSoundtrack": "VRGDG H3 Video Soundtrack (Song or Built-in)",
}
