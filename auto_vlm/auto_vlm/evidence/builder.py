"""Frame Evidence Package builder."""

from __future__ import annotations

from pathlib import Path

from auto_vlm import __version__
from auto_vlm.models.cases import EvaluationCase
from auto_vlm.models.evidence import EvidenceIntegrity, FrameEvidencePackage, VideoMetadata


DEFAULT_CONTEXT_OFFSETS: tuple[int, ...] = ()


def build_frame_evidence_package(
    case: EvaluationCase,
    sampled_frame: int,
    video_metadata: VideoMetadata,
    center_frame_image: str | Path,
    output_root: str | Path,
    context_image: str | Path | None = None,
    evidence_integrity: EvidenceIntegrity | None = None,
    qv_overlay_frame_image: str | Path | None = None,
    qv_overlay_context_image: str | Path | None = None,
    qv_video_metadata: VideoMetadata | None = None,
    raw_frame_image: str | Path | None = None,
    raw_context_image: str | Path | None = None,
    raw_video_metadata: VideoMetadata | None = None,
    json_snippet: str | Path | None = None,
    json_summary: str | None = None,
    context_offsets: tuple[int, ...] = DEFAULT_CONTEXT_OFFSETS,
    sampling_mode: str | None = None,
) -> FrameEvidencePackage:
    fps = video_metadata.fps or 0.0
    timestamp_sec = sampled_frame / fps if fps > 0 else 0.0
    package_id = FrameEvidencePackage.make_package_id(case.case_id, sampled_frame)
    output_root_path = Path(output_root)

    return FrameEvidencePackage(
        package_id=package_id,
        case_id=case.case_id,
        sampled_frame=sampled_frame,
        timestamp_sec=timestamp_sec,
        center_frame_image=Path(center_frame_image),
        context_image=Path(context_image) if context_image else None,
        video_metadata=video_metadata,
        project_type=case.project_type,
        source_case_metadata=case.source_case_metadata(),
        evidence_integrity=evidence_integrity or EvidenceIntegrity(),
        qv_overlay_frame_image=Path(qv_overlay_frame_image) if qv_overlay_frame_image else Path(center_frame_image),
        qv_overlay_context_image=Path(qv_overlay_context_image) if qv_overlay_context_image else None,
        qv_video_metadata=qv_video_metadata or video_metadata,
        raw_frame_image=Path(raw_frame_image) if raw_frame_image else None,
        raw_context_image=Path(raw_context_image) if raw_context_image else None,
        raw_video_metadata=raw_video_metadata,
        focus_feature=case.focus_feature,
        review_mode=case.review_mode,
        frame_metadata=case.frame_metadata,
        json_snippet=Path(json_snippet) if json_snippet else None,
        json_summary=json_summary,
        context_offsets=context_offsets,
        sampling_mode=sampling_mode,
        output_paths={
            "case_dir": str(output_root_path / "cases" / case.case_id),
            "center_frame_image": str(center_frame_image),
            "context_image": str(context_image) if context_image else "",
            "qv_overlay_frame_image": str(qv_overlay_frame_image or center_frame_image),
            "qv_overlay_context_image": str(qv_overlay_context_image) if qv_overlay_context_image else "",
            "raw_frame_image": str(raw_frame_image) if raw_frame_image else "",
            "raw_context_image": str(raw_context_image) if raw_context_image else "",
            "json_snippet": str(json_snippet) if json_snippet else "",
        },
        tool_version=__version__,
    )
