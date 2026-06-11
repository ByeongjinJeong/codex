"""Deterministic frame sampling."""

from __future__ import annotations

from dataclasses import dataclass, field

from auto_vlm.models.cases import DEFAULT_SAMPLING_START_FRAME, SamplingMode, SamplingRequest


@dataclass(frozen=True)
class SamplingResult:
    frames: tuple[int, ...]
    mode: SamplingMode
    warnings: tuple[str, ...] = field(default_factory=tuple)


def resolve_sampled_frames(request: SamplingRequest, frame_count: int) -> SamplingResult:
    if frame_count <= 0:
        return SamplingResult(
            frames=(),
            mode=request.mode,
            warnings=("video has no readable frames",),
        )

    if request.mode == SamplingMode.EXPLICIT_FRAMES:
        return _resolve_explicit_frames(request, frame_count)

    start, end, warnings = _resolve_bounds(request, frame_count)
    frames = _interval_frames(start=start, end=end, interval=request.sampling_frame or 0, include_start=request.start_frame is not None)
    return SamplingResult(frames=frames, mode=request.mode, warnings=tuple(warnings))


def _resolve_explicit_frames(request: SamplingRequest, frame_count: int) -> SamplingResult:
    warnings: list[str] = []
    valid_frames: list[int] = []
    max_frame = frame_count - 1

    for frame in request.frame_list:
        if frame > max_frame:
            warnings.append(f"frame {frame} is out of range and was skipped")
            continue
        valid_frames.append(frame)

    return SamplingResult(
        frames=tuple(valid_frames),
        mode=SamplingMode.EXPLICIT_FRAMES,
        warnings=tuple(warnings),
    )


def _resolve_bounds(request: SamplingRequest, frame_count: int) -> tuple[int, int, list[str]]:
    warnings: list[str] = []
    max_frame = frame_count - 1
    start = request.start_frame if request.start_frame is not None else DEFAULT_SAMPLING_START_FRAME
    end = request.end_frame if request.end_frame is not None else max_frame

    if start > max_frame:
        warnings.append("start_frame is beyond the video and was clamped to final frame")
        start = max_frame
    if end > max_frame:
        warnings.append("end_frame is beyond the video and was clamped to final frame")
        end = max_frame
    if start < 0:
        warnings.append("start_frame was clamped to 0")
        start = 0
    if end < 0:
        warnings.append("end_frame was clamped to 0")
        end = 0
    if start > end:
        warnings.append("sampling range became empty after clamping")
        return end, end, warnings

    return start, end, warnings


def _interval_frames(start: int, end: int, interval: int, include_start: bool = False) -> tuple[int, ...]:
    if interval <= 0:
        return ()
    if start == end:
        return (start,)

    first = start if include_start else max(start, interval)
    if first > end:
        return (end,)
    return tuple(range(first, end + 1, interval))
