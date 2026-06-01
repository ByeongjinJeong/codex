"""Evidence-side schemas for Auto VLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class JsonFrameMatchStatus(str, Enum):
    EXACT = "exact"
    MISSING_JSON_DIR = "missing_json_dir"
    MISSING_FRAME_JSON = "missing_frame_json"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class JsonParseStatus(str, Enum):
    OK = "ok"
    MISSING = "missing"
    MALFORMED = "malformed"
    NOT_CHECKED = "not_checked"


@dataclass(frozen=True)
class VideoMetadata:
    video_path: Path
    frame_count: int
    fps: float
    width: int
    height: int
    decoder_status: str = "ok"

    def __post_init__(self) -> None:
        object.__setattr__(self, "video_path", Path(self.video_path))
        if self.frame_count < 0:
            raise ValueError("frame_count cannot be negative")
        if self.fps < 0:
            raise ValueError("fps cannot be negative")
        if self.width < 0 or self.height < 0:
            raise ValueError("video dimensions cannot be negative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "video_path": str(self.video_path),
            "frame_count": self.frame_count,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "decoder_status": self.decoder_status,
        }


@dataclass(frozen=True)
class EvidenceIntegrity:
    raw_video_available: bool = False
    raw_qv_frame_count_match: bool | None = None
    raw_qv_fps_match: bool | None = None
    raw_qv_dimensions_match: bool | None = None
    json_available: bool = False
    json_frame_match_status: JsonFrameMatchStatus = JsonFrameMatchStatus.MISSING_JSON_DIR
    json_parse_status: JsonParseStatus = JsonParseStatus.MISSING
    json_offset_suspected: bool = False
    overlay_sync_suspected: bool = False
    visualizer_module_visibility_unknown: bool = True
    module_may_be_disabled: bool = False
    raw_output_exists_but_not_drawn_possible: bool = False
    integrity_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "integrity_notes", tuple(self.integrity_notes))

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_video_available": self.raw_video_available,
            "raw_qv_frame_count_match": self.raw_qv_frame_count_match,
            "raw_qv_fps_match": self.raw_qv_fps_match,
            "raw_qv_dimensions_match": self.raw_qv_dimensions_match,
            "json_available": self.json_available,
            "json_frame_match_status": self.json_frame_match_status.value,
            "json_parse_status": self.json_parse_status.value,
            "json_offset_suspected": self.json_offset_suspected,
            "overlay_sync_suspected": self.overlay_sync_suspected,
            "visualizer_module_visibility_unknown": self.visualizer_module_visibility_unknown,
            "module_may_be_disabled": self.module_may_be_disabled,
            "raw_output_exists_but_not_drawn_possible": self.raw_output_exists_but_not_drawn_possible,
            "integrity_notes": list(self.integrity_notes),
        }


@dataclass(frozen=True)
class FeatureEvidencePacket:
    package_id: str
    feature: str
    raw_frame_image: Path | None = None
    qv_overlay_frame_image: Path | None = None
    ics_crop_image: Path | None = None
    ics_crop_status: str = "unavailable_or_unverified"
    bev_crop_image: Path | None = None
    bev_crop_status: str = "unavailable_or_unverified"
    json_snippet: Path | None = None
    json_summary: str = ""
    evaluated_issue_types: tuple[str, ...] = ()
    candidate_packet_paths: tuple[Path, ...] = ()
    packet_markdown: Path | None = None

    def __post_init__(self) -> None:
        if not self.package_id.strip():
            raise ValueError("package_id is required")
        if not self.feature.strip():
            raise ValueError("feature is required")
        object.__setattr__(self, "evaluated_issue_types", tuple(self.evaluated_issue_types))
        object.__setattr__(self, "candidate_packet_paths", tuple(Path(path) for path in self.candidate_packet_paths))
        for field_name in (
            "raw_frame_image",
            "qv_overlay_frame_image",
            "ics_crop_image",
            "bev_crop_image",
            "json_snippet",
            "packet_markdown",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, Path(value))

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "feature": self.feature,
            "raw_frame_image": str(self.raw_frame_image) if self.raw_frame_image else "",
            "qv_overlay_frame_image": str(self.qv_overlay_frame_image) if self.qv_overlay_frame_image else "",
            "ics_crop_image": str(self.ics_crop_image) if self.ics_crop_image else "",
            "ics_crop_status": self.ics_crop_status,
            "bev_crop_image": str(self.bev_crop_image) if self.bev_crop_image else "",
            "bev_crop_status": self.bev_crop_status,
            "json_snippet": str(self.json_snippet) if self.json_snippet else "",
            "json_summary": self.json_summary,
            "evaluated_issue_types": list(self.evaluated_issue_types),
            "candidate_packet_paths": [str(path) for path in self.candidate_packet_paths],
            "packet_markdown": str(self.packet_markdown) if self.packet_markdown else "",
        }


@dataclass(frozen=True)
class CandidateEvidencePacket:
    candidate_id: str
    package_id: str
    feature: str
    issue_type: str
    object_ids: tuple[str, ...]
    source: str
    raw_frame_image: Path | None = None
    qv_overlay_frame_image: Path | None = None
    ics_crop_image: Path | None = None
    ics_crop_status: str = "unavailable_or_unverified"
    bev_crop_image: Path | None = None
    bev_crop_status: str = "unavailable_or_unverified"
    candidate_json_values: Path | None = None
    full_json_snippet: Path | None = None
    json_summary: str = ""
    candidate_review_summary: str = ""
    packet_markdown: Path | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id is required")
        if not self.package_id.strip():
            raise ValueError("package_id is required")
        object.__setattr__(self, "object_ids", tuple(str(value) for value in self.object_ids))
        for field_name in (
            "raw_frame_image",
            "qv_overlay_frame_image",
            "ics_crop_image",
            "bev_crop_image",
            "candidate_json_values",
            "full_json_snippet",
            "packet_markdown",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, Path(value))

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "package_id": self.package_id,
            "feature": self.feature,
            "issue_type": self.issue_type,
            "object_ids": list(self.object_ids),
            "source": self.source,
            "raw_frame_image": str(self.raw_frame_image) if self.raw_frame_image else "",
            "qv_overlay_frame_image": str(self.qv_overlay_frame_image) if self.qv_overlay_frame_image else "",
            "ics_crop_image": str(self.ics_crop_image) if self.ics_crop_image else "",
            "ics_crop_status": self.ics_crop_status,
            "bev_crop_image": str(self.bev_crop_image) if self.bev_crop_image else "",
            "bev_crop_status": self.bev_crop_status,
            "candidate_json_values": str(self.candidate_json_values) if self.candidate_json_values else "",
            "full_json_snippet": str(self.full_json_snippet) if self.full_json_snippet else "",
            "json_summary": self.json_summary,
            "candidate_review_summary": self.candidate_review_summary,
            "packet_markdown": str(self.packet_markdown) if self.packet_markdown else "",
        }


@dataclass(frozen=True)
class FrameEvidencePackage:
    package_id: str
    case_id: str
    sampled_frame: int
    timestamp_sec: float
    center_frame_image: Path
    video_metadata: VideoMetadata
    project_type: str | None
    source_case_metadata: dict[str, Any]
    evidence_integrity: EvidenceIntegrity
    context_image: Path | None = None
    qv_overlay_frame_image: Path | None = None
    qv_overlay_context_image: Path | None = None
    qv_video_metadata: VideoMetadata | None = None
    raw_frame_image: Path | None = None
    raw_context_image: Path | None = None
    raw_video_metadata: VideoMetadata | None = None
    focus_feature: str = "ALL"
    review_mode: str = "gtless_single_frame"
    frame_metadata: dict[str, Any] = field(default_factory=dict)
    json_snippet: Path | None = None
    json_summary: str | None = None
    context_offsets: tuple[int, ...] = ()
    sampling_mode: str | None = None
    output_paths: dict[str, str] = field(default_factory=dict)
    feature_evidence_packets: tuple[FeatureEvidencePacket, ...] = ()
    candidate_evidence_packets: tuple[CandidateEvidencePacket, ...] = ()
    tool_version: str | None = None

    def __post_init__(self) -> None:
        if not self.package_id.strip():
            raise ValueError("package_id is required")
        if not self.case_id.strip():
            raise ValueError("case_id is required")
        if self.sampled_frame < 0:
            raise ValueError("sampled_frame cannot be negative")
        if self.timestamp_sec < 0:
            raise ValueError("timestamp_sec cannot be negative")

        object.__setattr__(self, "center_frame_image", Path(self.center_frame_image))
        for field_name in (
            "context_image",
            "qv_overlay_frame_image",
            "qv_overlay_context_image",
            "raw_frame_image",
            "raw_context_image",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, Path(value))
        if self.json_snippet is not None:
            object.__setattr__(self, "json_snippet", Path(self.json_snippet))
        object.__setattr__(self, "context_offsets", tuple(self.context_offsets))
        object.__setattr__(self, "feature_evidence_packets", tuple(self.feature_evidence_packets))
        object.__setattr__(self, "candidate_evidence_packets", tuple(self.candidate_evidence_packets))

    @classmethod
    def make_package_id(cls, case_id: str, sampled_frame: int) -> str:
        return f"{case_id}__frame_{sampled_frame:08d}"
