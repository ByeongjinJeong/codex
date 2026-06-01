from __future__ import annotations

from auto_vlm.sampling.sampler import resolve_sampled_frames
from auto_vlm.models.cases import SamplingMode, SamplingRequest


def test_frame_list_priority_skips_out_of_range_frames():
    result = resolve_sampled_frames(
        SamplingRequest(frame_list=(1, 99, 200), start_frame=10, end_frame=20, sampling_frame=None),
        frame_count=100,
    )

    assert result.mode == SamplingMode.EXPLICIT_FRAMES
    assert result.frames == (1, 99)
    assert "frame 200 is out of range and was skipped" in result.warnings


def test_range_sampling_uses_start_and_end():
    result = resolve_sampled_frames(
        SamplingRequest(start_frame=10, end_frame=20, sampling_frame=5),
        frame_count=100,
    )

    assert result.mode == SamplingMode.RANGE_INTERVAL
    assert result.frames == (10, 15, 20)


def test_full_video_interval_sampling_starts_at_interval():
    result = resolve_sampled_frames(SamplingRequest(sampling_frame=3), frame_count=10)

    assert result.mode == SamplingMode.FULL_VIDEO_INTERVAL
    assert result.frames == (3, 6, 9)


def test_range_bounds_are_clamped():
    result = resolve_sampled_frames(
        SamplingRequest(start_frame=8, end_frame=20, sampling_frame=5),
        frame_count=10,
    )

    assert result.frames == (8,)
    assert "end_frame is beyond the video and was clamped to final frame" in result.warnings


def test_short_video_returns_available_frames_only():
    result = resolve_sampled_frames(SamplingRequest(sampling_frame=20), frame_count=3)

    assert result.frames == (2,)


def test_unreadable_video_returns_empty_with_warning():
    result = resolve_sampled_frames(SamplingRequest(sampling_frame=20), frame_count=0)

    assert result.frames == ()
    assert result.warnings == ("video has no readable frames",)
