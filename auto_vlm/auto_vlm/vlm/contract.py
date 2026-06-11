"""Prompt payload contract for optional VLM evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from auto_vlm.models.evidence import FrameEvidencePackage
from auto_vlm.vlm.feature_context import build_feature_review_contexts
from auto_vlm.vlm.reference_context import load_adas_common_workflow, load_adas_must_not


def build_vlm_prompt_payload(package: FrameEvidencePackage) -> dict[str, Any]:
    if not isinstance(package, FrameEvidencePackage):
        raise TypeError("VLM prompt payload must be built from FrameEvidencePackage")

    feature_review_contexts = build_feature_review_contexts(package.focus_feature)
    adas_review_workflow = load_adas_common_workflow()
    adas_must_not = load_adas_must_not()

    return {
        "package_id": package.package_id,
        "case_id": package.case_id,
        "sampled_frame": package.sampled_frame,
        "timestamp_sec": package.timestamp_sec,
        "raw_frame_image": _path_string(package.raw_frame_image),
        "raw_video_metadata": package.raw_video_metadata.as_dict() if package.raw_video_metadata else None,
        "qv_overlay_frame_image": _path_string(package.qv_overlay_frame_image or package.center_frame_image),
        "qv_video_metadata": (package.qv_video_metadata or package.video_metadata).as_dict(),
        "center_frame_image": _path_string(package.center_frame_image),
        "video_metadata": package.video_metadata.as_dict(),
        "project_type": package.project_type,
        "focus_feature": package.focus_feature,
        "review_mode": package.review_mode,
        "gt_reference": {
            "lidar_overlay_path": package.source_case_metadata.get("lidar_overlay_path", ""),
            "lidar_json_dir": package.source_case_metadata.get("lidar_json_dir", ""),
            "lidar_json_path": package.source_case_metadata.get("lidar_json_path", ""),
        },
        "frame_metadata": package.frame_metadata,
        "json_summary": package.json_summary,
        "evaluation_scope": package.evaluation_scope,
        "json_snippet": _path_string(package.json_snippet),
        "evidence_integrity": package.evidence_integrity.as_dict(),
        "adas_review_workflow": adas_review_workflow,
        "adas_must_not": adas_must_not,
        "feature_review_contexts": [context.as_dict() for context in feature_review_contexts],
        "feature_evidence_packets": [
            packet.as_dict() for packet in package.feature_evidence_packets
        ],
        "instructions": {
            "must_separate": ["observed_evidence", "inference", "uncertainty"],
            "compare_order": [
                "describe the real scene from raw_frame_image",
                "describe the rendered ICS/image overlay from qv_overlay_frame_image",
                "compare raw scene against ICS overlay for visible missing, extra, or poorly fitted outputs",
                "inspect BEV/world-space overlay before using JSON physical values; JSON supports BEV and must not replace BEV inspection",
                "compare raw, ICS, and BEV/JSON evidence together against json_summary/json_snippet",
                "for each reviewed feature, scan every issue type listed in its feature_review_context before assigning pass/fail",
                "apply feature_review_contexts only after evidence inspection",
            ],
            "must_not": [
                "claim GT accuracy",
                "invent JSON values absent from json_summary or json_snippet",
                "treat weak evidence as confirmed SW issue",
                "treat reference documents as GT",
                "clear a feature as pass after checking only one or two coarse symptoms",
                "clear a feature as pass only because ICS/image overlay looks correct while ignoring BEV/world-space evidence",
                "assign feature or issue type before citing observed evidence",
            ],
        },
    }


def write_vlm_review_packet(package: FrameEvidencePackage, output_dir: str | Path) -> Path:
    payload = build_vlm_prompt_payload(package)
    output = Path(output_dir) / f"{package.package_id}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_review_packet(payload), encoding="utf-8")
    return output


def _path_string(path: Path | None) -> str:
    return str(path) if path else ""


def _render_review_packet(payload: dict[str, Any]) -> str:
    if payload["feature_evidence_packets"]:
        return _render_short_index_packet(payload)
    return "\n".join(
        [
            f"# VLM Review Packet: {payload['package_id']}",
            "",
            "## Evidence",
            "",
            f"- case_id: {payload['case_id']}",
            f"- sampled_frame: {payload['sampled_frame']}",
            f"- timestamp_sec: {payload['timestamp_sec']}",
            f"- raw_frame_image: {payload['raw_frame_image']}",
            f"- qv_overlay_frame_image: {payload['qv_overlay_frame_image']}",
            f"- json_snippet: {payload['json_snippet']}",
            f"- json_summary: {payload['json_summary']}",
            f"- evaluation_scope: {payload['evaluation_scope']}",
            f"- review_mode: {payload['review_mode']}",
            f"- lidar_overlay_path: {payload['gt_reference']['lidar_overlay_path']}",
            f"- lidar_json_dir: {payload['gt_reference']['lidar_json_dir']}",
            f"- lidar_json_path: {payload['gt_reference']['lidar_json_path']}",
            f"- evidence_integrity: {payload['evidence_integrity']}",
            "",
            "## ADAS Vision Review Workflow",
            "",
            *_bullet_lines(payload["adas_review_workflow"]),
            "",
            "Must not:",
            *_bullet_lines(payload["adas_must_not"]),
            "",
            "## Feature Review Context",
            "",
            *_render_feature_review_contexts(payload["feature_review_contexts"]),
            "",
            "## LLM/VLM Task",
            "",
            "Review the raw source frame, QV overlay frame, JSON summary, and integrity flags.",
            "Use review_mode to decide the evaluable issue scope: gtless_single_frame uses raw/QV/JSON only; gt_reference may use provided LiDAR overlay/JSON reference evidence.",
            "JSON physical values support the BEV overlay observation. They must not replace BEV overlay inspection.",
            "Use evaluation_scope only to decide whether an observed issue is reportable. It is not evidence that an issue exists.",
            "BEV/JSON can reveal physical-value issues only when JSON is used as support for inspected BEV evidence.",
            "Do not stop when ICS looks correct; BEV evidence can reveal physical-value issues in long/lat, C0-C3, heading, ID, range, class, confidence, or state.",
            "After evidence inspection, evaluate every issue type listed in each feature review context before assigning feature pass/fail.",
            "A feature-level pass means no defined issue type has observable evidence in raw/QV/JSON for that frame.",
            "Use the most specific issue type available; for example, prefer OD heading angle or OD BBOX duplication over generic OD FP when evidence supports it.",
            "Do not calculate GT accuracy. Do not invent JSON values.",
            "Separate observed evidence, inference, and uncertainty.",
            "",
            "## Required Output Schema",
            "",
            "```text",
            "review_mode: gtless_single_frame | gt_reference",
            "judgment: likely_issue | potential_issue | acceptable | sync_or_visualizer_issue | needs_more_evidence",
            "confidence: high | medium | low",
            "feature: OD | LD | RBD | TS | TL | ALL | unknown",
            "suspicious_type: FN | FP | misclassification | bbox_or_geometry_error | distance_or_position_error | value_jump | id_switch_or_duplication | update_failure | flicker | sync_or_overlay_mismatch | unclear",
            "review_priority: high | medium | low",
            "feature_results:",
            "  - feature: OD | LD | RBD | TS | TL",
            "    result: pass | fail",
            "    confidence: high | medium | low",
            "    evaluated_issue_types: [DEF-* ids evaluated in this review mode]",
            "    triggered_issue_types: [evaluated DEF-* ids judged present, or []]",
            "    summary:",
            "    observed_evidence: must explicitly cite raw frame evidence, QV overlay evidence, and JSON summary/snippet evidence for this feature",
            "    inference: explain why the cited evidence maps to pass/fail",
            "    uncertainty: state what remains limited by single-frame GT-less evidence",
            "summary:",
            "observed_evidence:",
            "inference:",
            "uncertainty:",
            "```",
            "",
        ]
    )


def _render_short_index_packet(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# VLM Review Index: {payload['package_id']}",
            "",
            "Use the feature packets as the primary VLM review input.",
            "This file is intentionally short so comprehensive review is procedural instead of one large prompt.",
            "",
            "## Frame Evidence",
            "",
            f"- case_id: {payload['case_id']}",
            f"- sampled_frame: {payload['sampled_frame']}",
            f"- raw_frame_image: {payload['raw_frame_image']}",
            f"- qv_overlay_frame_image: {payload['qv_overlay_frame_image']}",
            f"- json_snippet: {payload['json_snippet']}",
            f"- json_summary: {payload['json_summary']}",
            f"- evaluation_scope: {payload['evaluation_scope']}",
            "",
            "## Feature Sweep Packets",
            "",
            *_render_feature_evidence_packets(payload["feature_evidence_packets"]),
            "",
            "## Mandatory Review Order",
            "",
            "1. Complete every feature sweep packet for OD, LD, RBD, TS, and TL.",
            "2. Within each feature, read the Issue Evidence Strategy section. Do not apply one fixed plane order to every issue.",
            "3. Use raw context first, then follow the issue-specific order; geometry/range/heading/role issues may require BEV/VCS before ICS confirmation.",
            "4. Evaluate every listed DEF-* issue type before assigning feature pass/fail.",
            "5. Aggregate feature results into llm_review_results.json.",
            "",
            "JSON is the SW output being reviewed. Use it as supporting evidence, not as ground truth and not as a replacement for raw/ICS/BEV inspection.",
            "Evaluation scope annotations define reportability range only. They must not create or suppress issues without VLM evidence.",
            "",
            "## Required Output Shape",
            "",
            "```text",
            "feature_results:",
            "  - feature: OD",
            "    result: pass | fail",
            "    confidence: high | medium | low",
            "    evaluated_issue_types: [DEF-* ids evaluated]",
            "    triggered_issue_types: [DEF-* ids present, or []]",
            "    summary:",
            "    observed_evidence:",
            "    inference:",
            "    uncertainty:",
            "```",
            "",
        ]
    )


def _render_feature_evidence_packets(packets: list[dict[str, object]]) -> list[str]:
    if not packets:
        return ["- No feature packet generated."]
    lines: list[str] = []
    for packet in packets:
        issue_types = packet["evaluated_issue_types"]
        issue_count = len(issue_types) if isinstance(issue_types, list) else 0
        lines.extend(
            [
                f"### {packet['feature']}",
                "",
                f"- packet_markdown: {packet['packet_markdown']}",
                f"- evaluated_issue_type_count: {issue_count}",
                f"- raw_frame_image: {packet['raw_frame_image']}",
                f"- qv_overlay_frame_image: {packet['qv_overlay_frame_image']}",
                f"- json_snippet: {packet['json_snippet']}",
                f"- evaluation_scope: {packet.get('evaluation_scope', {})}",
                "",
            ]
        )
    return lines


def _render_feature_review_contexts(contexts: list[dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for context in contexts:
        feature = context["feature"]
        lines.extend(
            [
                f"### {feature}",
                "",
                "Reference sources:",
                *_bullet_lines(context["reference_sources"]),
                "",
                "QV/JSON interpretation:",
                *_bullet_lines(context["qv_json_interpretation"]),
                "",
                "Issue type guidance:",
                *_bullet_lines(context["issue_type_guidance"]),
                "",
                "Inspection checklist:",
                *_bullet_lines(context["inspection_checklist"]),
                "",
                "Must not:",
                *_bullet_lines(context["must_not"]),
                "",
            ]
        )
    return lines


def _bullet_lines(values: object) -> list[str]:
    if not isinstance(values, list):
        return [f"- {values}"]
    return [f"- {value}" for value in values]
