"""Batch engine orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from auto_vlm.conversion.raw_video import remux_h264_to_mp4
from auto_vlm.conversion.video import extract_center_frame, read_video_metadata
from auto_vlm.conversion.json_matcher import match_frame_json
from auto_vlm.evidence.builder import build_frame_evidence_package
from auto_vlm.evidence.candidate_packets import write_candidate_evidence_packets
from auto_vlm.evidence.feature_packets import write_feature_evidence_packets
from auto_vlm.inputs.excel import load_cases
from auto_vlm.sampling.sampler import resolve_sampled_frames
from auto_vlm.vlm.contract import write_vlm_review_packet
from auto_vlm.vlm.result_loader import ReviewResultLoadError, filter_results_for_packages, load_review_results
from auto_vlm.vlm.review_validator import (
    ReviewQualityReport,
    empty_review_quality_report,
    validate_review_quality,
)
from auto_vlm.vlm.review_tasks import write_review_tasks
from auto_vlm.models.evidence import EvidenceIntegrity, FrameEvidencePackage, VideoMetadata
from auto_vlm.models.results import PackageReviewResult
from auto_vlm.pipeline.manifest import write_run_manifest
from auto_vlm.reports.excel_report import write_result_xlsx
from auto_vlm.reports.html_report import write_summary_html
from auto_vlm.utils.errors import ToolError


@dataclass(frozen=True)
class EngineResult:
    packages: list[FrameEvidencePackage] = field(default_factory=list)
    errors: list[ToolError] = field(default_factory=list)
    result_xlsx: Path | None = None
    summary_html: Path | None = None
    manifest_json: Path | None = None
    review_tasks_json: Path | None = None
    review_results_json: Path | None = None
    review_results: dict[str, PackageReviewResult] = field(default_factory=dict)
    review_quality: ReviewQualityReport = field(default_factory=empty_review_quality_report)
    reused_artifact_packages: int = 0
    generated_artifact_packages: int = 0


def run_excel_batch(
    input_path: str | Path,
    output_dir: str | Path,
    review_results_path: str | Path | None = None,
    reuse_existing_artifacts: bool = False,
) -> EngineResult:
    output_root = Path(output_dir)
    adapter_result = load_cases(input_path)
    packages: list[FrameEvidencePackage] = []
    errors: list[ToolError] = list(adapter_result.errors)
    reused_artifact_packages = 0

    for case in adapter_result.cases:
        try:
            qv_video_metadata = read_video_metadata(case.qv_video_path or case.video_path)
        except ValueError as exc:
            errors.append(
                ToolError(
                    code="video_unreadable",
                    problem="video could not be read",
                    location=str(case.qv_video_path or case.video_path),
                    cause=str(exc),
                    fix="Check that qv_video_path/video_path points to a readable QV-rendered mp4 file.",
                    case_id=case.case_id,
                )
            )
            continue

        raw_video_metadata: VideoMetadata | None = None
        raw_video_path = _prepare_raw_video(case.raw_video_path, output_root, reuse_existing_artifacts)
        if raw_video_path:
            try:
                raw_video_metadata = read_video_metadata(raw_video_path)
            except ValueError as exc:
                errors.append(
                    ToolError(
                        code="raw_video_unreadable",
                        problem="raw h264 video could not be read",
                        location=str(raw_video_path),
                        cause=str(exc),
                        fix="Check that raw_video_path points to a readable source video or remuxable h264 file.",
                        case_id=case.case_id,
                    )
                )
                continue

        raw_sampling_count = (
            raw_video_metadata.frame_count
            if raw_video_metadata and raw_video_metadata.frame_count > 0
            else qv_video_metadata.frame_count
        )
        sampling_frame_count = min(qv_video_metadata.frame_count, raw_sampling_count)
        sampling = resolve_sampled_frames(case.sampling_request, sampling_frame_count)
        if not sampling.frames:
            errors.append(
                ToolError(
                    code="no_sampled_frames",
                    problem="no sampled frames were resolved",
                    location=str(case.qv_video_path or case.video_path),
                    cause="Sampler returned an empty frame list.",
                    fix="Check frame_list, sampling_frame, start_frame/end_frame, and video readability.",
                    case_id=case.case_id,
                )
            )
            continue

        for sampled_frame in sampling.frames:
            try:
                package, reused_artifacts = _build_sample_package(
                    case,
                    sampled_frame,
                    sampling.mode.value,
                    qv_video_metadata,
                    raw_video_metadata,
                    raw_video_path,
                    output_root,
                    reuse_existing_artifacts,
                )
                candidate_packets = write_candidate_evidence_packets(
                    package,
                    output_root / "cases" / case.case_id,
                )
                feature_packets = write_feature_evidence_packets(
                    package,
                    output_root / "cases" / case.case_id,
                    candidate_packets=candidate_packets,
                )
                package = replace(
                    package,
                    feature_evidence_packets=feature_packets,
                    candidate_evidence_packets=candidate_packets,
                )
                write_vlm_review_packet(
                    package,
                    output_root / "cases" / case.case_id / "vlm_packets",
                )
                packages.append(package)
                if reused_artifacts:
                    reused_artifact_packages += 1
            except ValueError as exc:
                errors.append(
                    ToolError(
                        code="frame_extraction_failed",
                        problem="sampled frame evidence could not be generated",
                        location=f"{case.video_path} frame {sampled_frame}",
                        cause=str(exc),
                        fix="Check that the sampled frame exists and the output directory is writable.",
                        case_id=case.case_id,
                    )
                )

    loaded_results: dict[str, PackageReviewResult] = {}
    review_tasks_json = write_review_tasks(output_root / "review_tasks.json", packages) if packages else None
    review_artifact = Path(review_results_path) if review_results_path else output_root / "llm_review_results.json"
    if review_artifact.exists():
        try:
            loaded_results = filter_results_for_packages(
                load_review_results(review_artifact),
                {package.package_id for package in packages},
                packages=packages,
            )
        except ReviewResultLoadError as exc:
            errors.append(
                ToolError(
                    code="llm_review_results_invalid",
                    problem="LLM review results could not be loaded",
                    location=str(review_artifact),
                    cause=str(exc),
                    fix="Fix llm_review_results.json so it matches generated package_id values and feature schema.",
                )
            )
    review_quality = validate_review_quality(packages, loaded_results)
    result_xlsx = None
    summary_html = None
    if loaded_results:
        result_xlsx = write_result_xlsx(
            output_root / "result.xlsx",
            packages,
            results=loaded_results,
            errors=errors,
            review_quality_status=review_quality.status,
        )
        summary_html = write_summary_html(
            output_root / "summary.html",
            packages,
            results=loaded_results,
            errors=errors,
            review_quality_status=review_quality.status,
        )
    else:
        _remove_stale_report(output_root / "result.xlsx")
        _remove_stale_report(output_root / "summary.html")
    manifest_json = write_run_manifest(
        output_root / "manifest.json",
        input_path=input_path,
        output_dir=output_root,
        packages=packages,
        errors=errors,
        result_xlsx=result_xlsx,
        summary_html=summary_html,
        review_tasks_json=review_tasks_json,
        review_results_json=review_artifact if review_artifact.exists() else None,
        review_results=loaded_results,
        review_quality=review_quality,
        reuse_existing_artifacts=reuse_existing_artifacts,
        reused_artifact_packages=reused_artifact_packages,
        generated_artifact_packages=len(packages) - reused_artifact_packages,
    )
    return EngineResult(
        packages=packages,
        errors=errors,
        result_xlsx=result_xlsx,
        summary_html=summary_html,
        manifest_json=manifest_json,
        review_tasks_json=review_tasks_json,
        review_results_json=review_artifact if review_artifact.exists() else None,
        review_results=loaded_results,
        review_quality=review_quality,
        reused_artifact_packages=reused_artifact_packages,
        generated_artifact_packages=len(packages) - reused_artifact_packages,
    )


def _prepare_raw_video(raw_video_path: Path | None, output_root: Path, reuse_existing_artifacts: bool = False) -> Path | None:
    if raw_video_path is None:
        return None
    raw_video_path = Path(raw_video_path)
    if raw_video_path.suffix.lower() != ".h264":
        return raw_video_path

    normalized_dir = output_root / "raw_video_cache"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = normalized_dir / f"{raw_video_path.stem}.raw.mp4"
    if reuse_existing_artifacts and normalized_path.exists():
        return normalized_path
    return remux_h264_to_mp4(raw_video_path, normalized_path)


def _remove_stale_report(path: Path) -> None:
    if path.exists():
        path.unlink()


def _build_sample_package(
    case,
    sampled_frame,
    sampling_mode,
    qv_video_metadata,
    raw_video_metadata,
    raw_video_path,
    output_root,
    reuse_existing_artifacts=False,
):
    case_dir = output_root / "cases" / case.case_id
    qv_frame_path = case_dir / "qv_frames" / f"frame_{sampled_frame:08d}.jpg"
    raw_frame_path = case_dir / "raw_frames" / f"frame_{sampled_frame:08d}.jpg"
    json_output_dir = case_dir / "json_snippets"

    reuse_images = reuse_existing_artifacts and _sample_artifacts_exist(
        qv_frame_path,
        raw_frame_path if raw_video_path else None,
    )
    if reuse_images:
        qv_frame = qv_frame_path
        raw_frame = raw_frame_path if raw_video_path else None
    else:
        qv_frame = extract_center_frame(case.qv_video_path or case.video_path, sampled_frame, qv_frame_path)
        raw_frame = None
        if raw_video_path:
            raw_frame = extract_center_frame(raw_video_path, sampled_frame, raw_frame_path)
    json_match = match_frame_json(case.json_dir, sampled_frame, json_output_dir, focus_feature=case.focus_feature)
    evidence_integrity = _merge_alignment_integrity(json_match.evidence_integrity, qv_video_metadata, raw_video_metadata)

    return (
        build_frame_evidence_package(
            case=case,
            sampled_frame=sampled_frame,
            video_metadata=qv_video_metadata,
            center_frame_image=qv_frame,
            output_root=output_root,
            evidence_integrity=evidence_integrity,
            qv_overlay_frame_image=qv_frame,
            qv_video_metadata=qv_video_metadata,
            raw_frame_image=raw_frame,
            raw_video_metadata=raw_video_metadata,
            json_snippet=json_match.json_snippet,
            json_summary=json_match.json_summary,
            context_offsets=(),
            sampling_mode=sampling_mode,
        ),
        reuse_images,
    )


def _sample_artifacts_exist(*paths: Path | None) -> bool:
    return all(path is None or path.exists() for path in paths)


def _merge_alignment_integrity(
    base: EvidenceIntegrity,
    qv_video_metadata: VideoMetadata,
    raw_video_metadata: VideoMetadata | None,
) -> EvidenceIntegrity:
    notes = list(base.integrity_notes)
    if raw_video_metadata is None:
        notes.append("raw h264 video was not provided; AI/VLM cannot compare real scene against overlay")
        return EvidenceIntegrity(
            raw_video_available=False,
            raw_qv_frame_count_match=None,
            raw_qv_fps_match=None,
            raw_qv_dimensions_match=None,
            json_available=base.json_available,
            json_frame_match_status=base.json_frame_match_status,
            json_parse_status=base.json_parse_status,
            json_offset_suspected=base.json_offset_suspected,
            overlay_sync_suspected=True,
            visualizer_module_visibility_unknown=base.visualizer_module_visibility_unknown,
            module_may_be_disabled=base.module_may_be_disabled,
            raw_output_exists_but_not_drawn_possible=base.raw_output_exists_but_not_drawn_possible,
            integrity_notes=tuple(notes),
        )

    frame_count_match = (
        qv_video_metadata.frame_count == raw_video_metadata.frame_count
        if raw_video_metadata.frame_count > 0
        else None
    )
    fps_match = abs(qv_video_metadata.fps - raw_video_metadata.fps) < 0.01
    dimensions_match = (
        qv_video_metadata.width == raw_video_metadata.width
        and qv_video_metadata.height == raw_video_metadata.height
    )
    overlay_sync_suspected = base.overlay_sync_suspected or frame_count_match is False or not fps_match
    if frame_count_match is False:
        notes.append("raw h264 and QV mp4 frame counts differ")
    if frame_count_match is None:
        notes.append("raw h264 frame count is unknown; alignment is based on requested frame index")
    if not fps_match:
        notes.append("raw h264 and QV mp4 fps differ")
    if not dimensions_match:
        notes.append("raw h264 and QV mp4 dimensions differ")

    return EvidenceIntegrity(
        raw_video_available=True,
        raw_qv_frame_count_match=frame_count_match,
        raw_qv_fps_match=fps_match,
        raw_qv_dimensions_match=dimensions_match,
        json_available=base.json_available,
        json_frame_match_status=base.json_frame_match_status,
        json_parse_status=base.json_parse_status,
        json_offset_suspected=base.json_offset_suspected,
        overlay_sync_suspected=overlay_sync_suspected,
        visualizer_module_visibility_unknown=base.visualizer_module_visibility_unknown,
        module_may_be_disabled=base.module_may_be_disabled,
        raw_output_exists_but_not_drawn_possible=base.raw_output_exists_but_not_drawn_possible,
        integrity_notes=tuple(notes),
    )
