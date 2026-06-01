"""Input-side schemas for Auto VLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


DEFAULT_SAMPLING_FRAME = 50
SUPPORTED_FOCUS_FEATURES = {
    "ALL",
    "OD",
    "LD",
    "RBD",
    "TS",
    "TL",
}


class SamplingMode(str, Enum):
    EXPLICIT_FRAMES = "explicit_frames"
    RANGE_INTERVAL = "range_interval"
    FULL_VIDEO_INTERVAL = "full_video_interval"


def _require_non_empty(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def normalize_review_features(value: str | None) -> str:
    if not value or not value.strip():
        return "ALL"
    parts = [part.strip().upper() for part in value.split(",") if part.strip()]
    if not parts:
        return "ALL"
    if "ALL" in parts:
        if len(parts) > 1:
            raise ValueError("focus_feature cannot combine ALL with specific features")
        return "ALL"
    unsupported = sorted(set(parts) - SUPPORTED_FOCUS_FEATURES)
    if unsupported:
        supported = ", ".join(sorted(SUPPORTED_FOCUS_FEATURES))
        raise ValueError(f"focus_feature must contain only: {supported}")
    return ",".join(dict.fromkeys(parts))


@dataclass(frozen=True)
class SamplingRequest:
    frame_list: tuple[int, ...] = ()
    start_frame: int | None = None
    end_frame: int | None = None
    sampling_frame: int | None = DEFAULT_SAMPLING_FRAME

    def __post_init__(self) -> None:
        normalized_frames = tuple(dict.fromkeys(self.frame_list))
        object.__setattr__(self, "frame_list", normalized_frames)
        if normalized_frames and self.sampling_frame == DEFAULT_SAMPLING_FRAME:
            object.__setattr__(self, "sampling_frame", None)

        if normalized_frames and self.sampling_frame is not None:
            raise ValueError("frame_list and sampling_frame cannot both be provided")
        if not normalized_frames and self.sampling_frame is None:
            raise ValueError("either frame_list or sampling_frame is required")
        if self.sampling_frame is not None and self.sampling_frame <= 0:
            raise ValueError("sampling_frame must be greater than 0")
        for frame in normalized_frames:
            if frame < 0:
                raise ValueError("frame_list cannot contain negative frames")
        if self.start_frame is not None and self.start_frame < 0:
            raise ValueError("start_frame cannot be negative")
        if self.end_frame is not None and self.end_frame < 0:
            raise ValueError("end_frame cannot be negative")
        if (
            self.start_frame is not None
            and self.end_frame is not None
            and self.start_frame > self.end_frame
        ):
            raise ValueError("start_frame cannot be greater than end_frame")

    @property
    def mode(self) -> SamplingMode:
        if self.frame_list:
            return SamplingMode.EXPLICIT_FRAMES
        if self.start_frame is not None or self.end_frame is not None:
            return SamplingMode.RANGE_INTERVAL
        return SamplingMode.FULL_VIDEO_INTERVAL


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    video_path: Path
    sampling_request: SamplingRequest
    raw_video_path: Path | None = None
    qv_video_path: Path | None = None
    input_source_type: str | None = None
    input_source_path: Path | None = None
    json_dir: Path | None = None
    lidar_overlay_path: Path | None = None
    lidar_json_dir: Path | None = None
    lidar_json_path: Path | None = None
    project_type: str | None = None
    focus_feature: str = "ALL"
    frame_metadata: dict[str, Any] = field(default_factory=dict)
    memo: str | None = None
    external_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _require_non_empty(self.case_id, "case_id"))
        object.__setattr__(self, "video_path", Path(self.video_path))
        if self.raw_video_path is not None:
            object.__setattr__(self, "raw_video_path", Path(self.raw_video_path))
        qv_video_path = Path(self.qv_video_path) if self.qv_video_path is not None else Path(self.video_path)
        object.__setattr__(self, "qv_video_path", qv_video_path)

        object.__setattr__(self, "focus_feature", normalize_review_features(self.focus_feature))

        if self.input_source_path is not None:
            object.__setattr__(self, "input_source_path", Path(self.input_source_path))
        if self.json_dir is not None:
            object.__setattr__(self, "json_dir", Path(self.json_dir))
        if self.lidar_overlay_path is not None:
            object.__setattr__(self, "lidar_overlay_path", Path(self.lidar_overlay_path))
        if self.lidar_json_dir is not None:
            object.__setattr__(self, "lidar_json_dir", Path(self.lidar_json_dir))
        if self.lidar_json_path is not None:
            object.__setattr__(self, "lidar_json_path", Path(self.lidar_json_path))

    @property
    def review_mode(self) -> str:
        if self.lidar_overlay_path is not None or self.lidar_json_dir is not None or self.lidar_json_path is not None:
            return "gt_reference"
        return "gtless_single_frame"

    def source_case_metadata(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "video_path": str(self.video_path),
            "raw_video_path": str(self.raw_video_path) if self.raw_video_path else None,
            "qv_video_path": str(self.qv_video_path) if self.qv_video_path else None,
            "input_source_type": self.input_source_type,
            "input_source_path": str(self.input_source_path) if self.input_source_path else None,
            "json_dir": str(self.json_dir) if self.json_dir else None,
            "lidar_overlay_path": str(self.lidar_overlay_path) if self.lidar_overlay_path else None,
            "lidar_json_dir": str(self.lidar_json_dir) if self.lidar_json_dir else None,
            "lidar_json_path": str(self.lidar_json_path) if self.lidar_json_path else None,
            "review_mode": self.review_mode,
            "project_type": self.project_type,
            "focus_feature": self.focus_feature,
            "frame_metadata": self.frame_metadata,
            "memo": self.memo,
            "external_metadata": self.external_metadata,
        }
