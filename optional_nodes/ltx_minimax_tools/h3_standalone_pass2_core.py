"""H3 pass two in overlapping windows, matching the Video Builder's window algorithm."""

from typing import Any, Dict, List, Optional, Tuple

import torch
import comfy.model_management
import comfy.utils
from comfy.nested_tensor import NestedTensor
from comfy_extras.nodes_custom_sampler import Guider_Basic, Noise_RandomNoise, SamplerCustomAdvanced

FPS = 24
MIN_WINDOW_TOKENS = 7
LOG_PREFIX = "[VRGDG Standalone H3 Pass 2]"
UPSCALE_MODES = ("per_window", "whole_clip")
OVERLAP_MODES = ("locked", "crossfade")


def av_parts(latent: dict) -> tuple:
    """Validate the native H3 AV boundary without changing its tensor layout."""
    samples = latent["samples"]
    if not getattr(samples, "is_nested", False):
        raise ValueError("Connect a joint MiniMax H3 video+audio latent, before AV separation.")
    video, audio = samples.unbind()
    if video.ndim != 5 or video.shape[1] != 24 or audio.ndim != 4 or audio.shape[1:3] != (32, 2):
        raise ValueError("Expected H3 video [B,24,T,H,W] and audio [B,32,2,T40].")
    return video, audio


def frame_at(token: int) -> int:
    """Pixel-frame start of an H3 token on the 1,4,4,4,4 temporal cycle."""
    groups, tail = divmod(token, 5)
    return groups * 17 + (0 if tail == 0 else 1 + (tail - 1) * 4)


def chunk_conditioning(conditioning: list, frame_start: int, frame_end: int,
                       height: int, width: int) -> list:
    """Keep global references; clip timed video/audio guides and rebase their timestamps."""
    result = []
    for embedding, metadata in conditioning:
        meta = metadata.copy()
        if "minimax_keyframes" in meta:
            guides = []
            for guide in meta["minimax_keyframes"]:
                origin = guide["resolved_frame_index"]
                # The two modalities can have different lengths; crop and anchor each separately.
                video = guide.get("latent")
                if video is not None:
                    count = video.shape[2]
                    indices = [i for i in range(count)
                               if origin + frame_at(i) < frame_end
                               and origin + frame_at(i + 1) > frame_start]
                    if indices:
                        first, last = indices[0] // 5 * 5, indices[-1] + 1
                        item = {k: v for k, v in guide.items() if k not in ("latent", "audio_latent")}
                        item["resolved_frame_index"] = origin + frame_at(first) - frame_start
                        item["latent"] = comfy.utils.common_upscale(
                            video[:, :, first:last].clone(), width, height, "bilinear", "disabled")
                        guides.append(item)
                audio = guide.get("audio_latent")
                if audio is not None:
                    first = max(0, round((frame_start - origin) * 40 / 24))
                    last = min(audio.shape[-1], round((frame_end - origin) * 40 / 24))
                    if last > first:
                        item = {k: v for k, v in guide.items() if k not in ("latent", "audio_latent")}
                        item["resolved_frame_index"] = origin + first * 24 / 40 - frame_start
                        item["audio_latent"] = audio[..., first:last].clone()
                        guides.append(item)
            meta["minimax_keyframes"] = guides
        result.append([embedding, meta])
    return result


def join_chunk(assembled: torch.Tensor, chunk: torch.Tensor, start: int, covered: int,
               mode: str) -> int:
    """Merge on CPU in-place; locked history is never overwritten."""
    overlap = max(0, covered - start)
    if overlap and mode == "crossfade":
        weight = torch.linspace(0, 1, overlap + 2, dtype=chunk.dtype)[1:-1].view(1, 1, -1, 1, 1)
        old = assembled[:, :, start:covered]
        old.lerp_(chunk[:, :, :overlap], weight)
    end = start + chunk.shape[2]
    assembled[:, :, covered:end] = chunk[:, :, overlap:]
    return end


def tokens_per_latent_frame(height: int, width: int) -> int:
    """Video tokens one latent frame costs. H3 patches the latent 2x2 and pads an odd side up to the patch size, so a
    68x120 latent is 34x60 = 2040 tokens and a 69x121 latent is 35x61 = 2135."""
    return max(1, ((height + 1) // 2) * ((width + 1) // 2))


def budget_window_tokens(max_window_tokens: int, per_frame: int) -> Tuple[int, str]:
    """``(latent frames per window, note)`` for a token budget.

    A budget of 0 is "off" and returns 0 (the caller then uses seconds). A positive budget never falls back to
    seconds: one too small for even the smallest window returns that window and a note that says so.
    """
    if max_window_tokens <= 0:
        return 0, ""
    frames = int(max_window_tokens) // max(1, per_frame)
    if frames >= MIN_WINDOW_TOKENS:
        return frames, ""
    return MIN_WINDOW_TOKENS, (
        f"max_window_tokens {int(max_window_tokens)} is below the smallest supported window "
        f"({MIN_WINDOW_TOKENS} latent frames = {MIN_WINDOW_TOKENS * per_frame} video tokens at {per_frame} tokens/frame); "
        "using that size."
    )


def window_plan(
    total_tokens: int,
    seconds: float,
    overlap_seconds: float,
    trim_seconds: float = 0.0,
    window_tokens: int = 0,
) -> List[Tuple[int, int, int]]:
    """Phase-aligned windows as ``(start, end, keep_end)``.

    Starts are multiples of 5 and lengths are ``5k + 2``. ``keep_end`` is where a window stops being final: the tail
    ``end - keep_end`` tokens were sampled with no future context, so they are thrown away and the next window redoes
    them with refined history on the left and real content on the right. The last window keeps everything.
    ``trim_seconds`` is snapped to whole 5-token groups (0.708 s each) and always leaves at least 7 tokens of locked
    history, so an overlap too short for it trims nothing. ``window_tokens`` (latent frames per window, from a token
    budget) overrides ``seconds`` when above zero.
    """
    if total_tokens < 2 or total_tokens % 5 != 2:
        raise ValueError("The pass-one H3 latent must contain 5k+2 video tokens (17k+5 frames).")
    if window_tokens > 0:
        groups = max(1, (int(window_tokens) - 2) // 5)
    else:
        groups = max(1, round((seconds * FPS - 5) / 17))
    overlap_groups = min(groups - 1, max(0, round((overlap_seconds * FPS - 5) / 17)))
    trim_groups = min(max(0, overlap_groups - 1), max(0, round(trim_seconds * FPS / 17)))
    window = groups * 5 + 2
    stride = (groups - overlap_groups) * 5
    result: List[Tuple[int, int, int]] = []
    start = 0
    while True:
        end = min(total_tokens, start + window)
        last = end == total_tokens
        result.append((start, end, end if last else end - trim_groups * 5))
        if last:
            return result
        start += stride


def cuda_peak_gb() -> Optional[float]:
    """Peak allocated VRAM in GB since the last reset, or None without CUDA."""
    return torch.cuda.max_memory_allocated() / 2 ** 30 if torch.cuda.is_available() else None


def cuda_reset_peak() -> None:
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def format_gb(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.1f} GB"


def run_chunks(
    latent: Dict[str, Any], model: Any, conditioning: List[Any], upscale_model: Dict[str, Any],
    upscaler: Any, sampler: Any, sigmas: torch.Tensor, scale: float,
    chunk_seconds: float, overlap_seconds: float, overlap_mode: str, seed: int, *,
    tail_trim_seconds: float = 0.0, max_window_tokens: int = 0, upscale_mode: str = "per_window",
) -> Tuple[Dict[str, Any], str]:
    """Upscale, then sample each window, retaining only current work and the CPU assembly.

    ``upscale_mode`` ``per_window`` upscales only the current window, so the learned upscaler never holds more than
    one window. ``whole_clip`` runs it once over the entire first-pass clip first and cuts windows from the result.
    ``max_window_tokens`` sizes windows by video tokens instead of seconds (0 is off).
    The report gives the PyTorch-allocated peak VRAM of the upscale and of the sampling of every window.
    """
    if upscale_mode not in UPSCALE_MODES:
        raise ValueError(f"upscale_mode must be per_window or whole_clip, got {upscale_mode!r}.")
    if overlap_mode not in OVERLAP_MODES:
        raise ValueError(f"overlap_mode must be locked or crossfade, got {overlap_mode!r}.")
    video, audio = av_parts(latent)
    video = video.to(device="cpu")
    audio = audio.to(device="cpu")
    up_height, up_width = round(video.shape[-2] * scale), round(video.shape[-1] * scale)
    per_frame = tokens_per_latent_frame(up_height, up_width)
    window_tokens, budget_note = budget_window_tokens(int(max_window_tokens), per_frame)
    plan = window_plan(video.shape[2], chunk_seconds, overlap_seconds, tail_trim_seconds, window_tokens)
    whole = None
    report: List[str] = []
    if budget_note:
        print(f"{LOG_PREFIX} {budget_note}")
        report.append(budget_note)
    if upscale_mode == "whole_clip":
        cuda_reset_peak()
        whole = upscaler.upscale({"samples": video.clone()}, upscale_model, scale)[0]["samples"].to(device="cpu")
        if whole.shape[2] != video.shape[2]:
            raise ValueError("The learned upscaler changed the number of video tokens.")
        line = f"Whole-clip upscale: peak VRAM {format_gb(cuda_peak_gb())} (PyTorch allocated)."
        print(f"{LOG_PREFIX} {line}")
        report.append(line)
    assembled: Optional[torch.Tensor] = None
    covered = 0
    first = plan[0]
    summary = (
        f"Plan: {len(plan)} windows of {first[1] - first[0]} tokens x {per_frame} tokens/frame "
        f"= {(first[1] - first[0]) * per_frame} video tokens each; "
        f"upscale {upscale_mode}; tail trim {first[1] - first[2] if len(plan) > 1 else 0} tokens."
    )
    print(f"{LOG_PREFIX} {summary}")
    report.insert(0, summary)
    progress = comfy.utils.ProgressBar(len(plan))
    for index, (start, end, keep_end) in enumerate(plan):
        comfy.model_management.throw_exception_if_processing_interrupted()
        frame_start, frame_end = frame_at(start), frame_at(end)
        audio_start = round(frame_start * 40 / FPS)
        audio_end = round(frame_end * 40 / FPS)
        chunk_audio = audio[..., audio_start:audio_end].clone()
        if chunk_audio.shape[-1] != audio_end - audio_start:
            raise ValueError("First-pass audio latent does not cover the video's complete duration.")
        message = (
            f"Chunk {index + 1}/{len(plan)}: {frame_start / FPS:.3f}-{frame_end / FPS:.3f}s, "
            f"video tokens {start}:{end} (keeps to {keep_end}), audio ticks {audio_start}:{audio_end}"
        )
        print(f"{LOG_PREFIX} {message}")
        upscale_peak = None
        if whole is not None:
            upscaled = whole[:, :, start:end].clone()
        else:
            cuda_reset_peak()
            upscaled = upscaler.upscale(
                {"samples": video[:, :, start:end].clone()}, upscale_model, scale)[0]["samples"]
            upscaled = upscaled.to(device="cpu")
            upscale_peak = cuda_peak_gb()
        if assembled is None:
            assembled = torch.empty(
                (*upscaled.shape[:2], video.shape[2], *upscaled.shape[3:]), dtype=upscaled.dtype, device="cpu")
        overlap = max(0, covered - start)
        locked = overlap if overlap_mode == "locked" else 0
        video_mask = torch.ones_like(upscaled)
        if locked:
            upscaled[:, :, :locked] = assembled[:, :, start:start + locked]
            video_mask[:, :, :locked] = 0
        piece = {
            "samples": NestedTensor((upscaled, chunk_audio)),
            "noise_mask": NestedTensor((video_mask, torch.zeros_like(chunk_audio))),
        }
        cond = chunk_conditioning(conditioning, frame_start, frame_end, *upscaled.shape[-2:])
        guider = Guider_Basic(model)
        guider.set_conds(cond)
        noise = Noise_RandomNoise((seed + start) % (1 << 64))
        cuda_reset_peak()
        sampled = SamplerCustomAdvanced.execute(noise, guider, sampler, sigmas, piece)[0]
        sample_peak = cuda_peak_gb()
        refined = sampled["samples"].unbind()[0].to(device="cpu")
        covered = join_chunk(
            assembled, refined[:, :, :keep_end - start], start, covered, overlap_mode)
        # The counters are reset before each stage, so the two numbers are separate peaks, not one combined peak.
        stages = f"sampling {format_gb(sample_peak)}" if upscale_peak is None else (
            f"upscale {format_gb(upscale_peak)}, sampling {format_gb(sample_peak)}")
        report.append(f"{message}; peak VRAM (PyTorch allocated) {stages}")
        print(f"{LOG_PREFIX} Chunk {index + 1}/{len(plan)} peak VRAM (PyTorch allocated) {stages}")
        # Do not retain the previous sampler/guider's GPU work while upscaling the next window.
        del sampled, refined, piece, guider, cond, upscaled, video_mask, chunk_audio
        progress.update(1)
    if covered != video.shape[2]:
        raise RuntimeError(f"Assembled {covered} of {video.shape[2]} video tokens.")
    result = {"samples": NestedTensor((assembled, audio.clone()))}
    report.append(
        f"Assembled {video.shape[2]} tokens / {frame_at(video.shape[2])} frames; "
        f"{overlap_mode} overlap; first-pass audio preserved exactly."
    )
    return result, "\n".join(report)
