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
        "review_cues": _review_cues(package.json_summary or "", package.focus_feature),
        "json_snippet": _path_string(package.json_snippet),
        "evidence_integrity": package.evidence_integrity.as_dict(),
        "adas_review_workflow": adas_review_workflow,
        "adas_must_not": adas_must_not,
        "feature_review_contexts": [context.as_dict() for context in feature_review_contexts],
        "feature_evidence_packets": [
            packet.as_dict() for packet in package.feature_evidence_packets
        ],
        "candidate_evidence_packets": [
            packet.as_dict() for packet in package.candidate_evidence_packets
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
            f"- review_mode: {payload['review_mode']}",
            f"- lidar_overlay_path: {payload['gt_reference']['lidar_overlay_path']}",
            f"- lidar_json_dir: {payload['gt_reference']['lidar_json_dir']}",
            f"- lidar_json_path: {payload['gt_reference']['lidar_json_path']}",
            f"- evidence_integrity: {payload['evidence_integrity']}",
            "",
            "## Machine-Detected Review Cues",
            "",
            *_bullet_lines(payload["review_cues"]),
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
            "## Candidate Evidence Packets",
            "",
            *_render_candidate_evidence_packets(payload["candidate_evidence_packets"]),
            "",
            "## LLM/VLM Task",
            "",
            "Review the raw source frame, QV overlay frame, JSON summary, and integrity flags.",
            "Use review_mode to decide the evaluable issue scope: gtless_single_frame uses raw/QV/JSON only; gt_reference may use provided LiDAR overlay/JSON reference evidence.",
            "For each candidate, follow this order: raw observation, ICS observation, BEV overlay observation, JSON support check, then decision.",
            "JSON physical values support the BEV overlay observation. They must not replace BEV overlay inspection.",
            "BEV/JSON can reveal physical-value issues only when JSON is used as support for inspected BEV evidence.",
            "Do not stop when ICS looks correct; BEV evidence can reveal physical-value issues in long/lat, C0-C3, heading, ID, range, class, confidence, or state.",
            "After evidence inspection, evaluate every issue type listed in each feature review context before assigning feature pass/fail.",
            "Treat machine-detected review cues as required checks: either cite them as an issue or explain why the visual/JSON evidence clears them.",
            "For each machine-detected candidate, write candidate_adjudications with raw_observation, ics_observation, bev_observation, json_observation, decision, decision_reason, and uncertainty.",
            "Also include checked_planes for compatibility; raw, ics, bev_vcs, and json must all be present when those evidence planes are readable.",
            "For OD_BBOX_DUP, issue only when raw/ICS and BEV overlay both support same-object duplicate. Clear when BEV overlay clearly separates the objects. Mark uncertain when BEV overlay is unreadable or unavailable.",
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
            "    candidate_adjudications:",
            "      - candidate_id: OD_BBOX_DUP_<left_id>_<right_id>",
            "        feature: OD",
            "        issue_type: DEF-OD-BBOX-DUP",
            "        object_ids: [<left_id>, <right_id>]",
            "        decision: issue | cleared | uncertain",
            "        result: issue | cleared | uncertain",
            "        checked_planes: [raw, ics, bev_vcs, json]",
            "        raw_observation:",
            "        ics_observation:",
            "        bev_observation:",
            "        json_observation:",
            "        decision_reason:",
            "        summary:",
            "        observed_evidence:",
            "        inference:",
            "        uncertainty:",
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
            "Use the feature packets as the primary LLM input, then use candidate packets for focused deep dives.",
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
            "",
            "## Feature Sweep Packets",
            "",
            *_render_feature_evidence_packets(payload["feature_evidence_packets"]),
            "",
            "## Candidate Deep-Dive Packets",
            "",
            *_render_candidate_evidence_packets(payload["candidate_evidence_packets"]),
            "## Mandatory Review Order",
            "",
            "1. Complete every feature sweep packet for OD, LD, RBD, TS, and TL.",
            "2. Within each feature, read the Issue Evidence Strategy section. Do not apply one fixed plane order to every issue.",
            "3. Use raw context first, then follow the issue-specific order; geometry/range/heading/role issues may require BEV/VCS before ICS confirmation.",
            "4. Evaluate every listed DEF-* issue type before assigning feature pass/fail.",
            "5. Open candidate deep-dive packets for machine-detected cues and adjudicate them explicitly.",
            "6. Aggregate feature results into llm_review_results.json.",
            "",
            "JSON is the SW output being reviewed. Use it as supporting evidence, not as ground truth and not as a replacement for raw/ICS/BEV inspection.",
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
            "    candidate_adjudications:",
            "      - candidate_id:",
            "        feature:",
            "        issue_type:",
            "        object_ids:",
            "        decision: issue | cleared | uncertain",
            "        result: issue | cleared | uncertain",
            "        checked_planes: [raw, ics, bev_vcs, json]",
            "        raw_observation:",
            "        ics_observation:",
            "        bev_observation:",
            "        json_observation:",
            "        decision_reason:",
            "        uncertainty:",
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
                "",
            ]
        )
    return lines


def _review_cues(json_summary: str, focus_feature: str) -> list[str]:
    """Lift compact json_summary hints into explicit review obligations."""
    cues: list[str] = []
    selected = (focus_feature or "ALL").upper()
    if selected in {"ALL", "OD"}:
        if "OD_heading_samples=" in json_summary:
            cues.append(
                "OD_heading_samples is present. Explicitly evaluate DEF-OD-HEADING: OD / Heading Angle before clearing OD. Compare the visible travel direction in the raw frame with the BEV/VCS object orientation; if a straight-driving vehicle is output with a visibly rotated or wrong BEV heading, trigger DEF-OD-HEADING even when the bbox-fit issue is also present."
            )
        if "OD_bbox_overlap_candidates=" in json_summary:
            cues.append(
                "OD_bbox_overlap_candidates is present. Create one candidate_adjudication per pair for DEF-OD-BBOX-DUP. Judge each pair using raw, ICS, BEV/VCS, and JSON together. ICS/image overlap is only a review cue, never sufficient evidence for duplication. Mark issue only when raw scene and BEV/VCS support the same physical object or same world-space location being output twice. If the objects are visually different, naturally overlap by perspective, or BEV/VCS separates them, clear that pair."
            )
        if "OD_large_bbox_candidates=" in json_summary:
            cues.append(
                "OD_large_bbox_candidates is present. Explicitly evaluate DEF-OD-BBOX-FIT: OD / Bounding box fit before clearing OD. Large image coverage is only a review cue, never sufficient evidence for a bbox-fit issue. Clear the candidate when the object is a near-field large vehicle/object, partially out of image, or otherwise expected to occupy a large image area unless raw/QV geometry visibly extends beyond the real object shape. If the bad fit is caused by a rotated projection or wrong object orientation, also evaluate and trigger DEF-OD-HEADING instead of reporting only BBOX-FIT."
            )
    if selected in {"ALL", "RBD"} and "road_edges=0" in json_summary:
        cues.append(
            "road_edges=0. If the raw/QV frame shows a road edge or boundary that should be output, evaluate DEF-LD-RBD-FN for RBD."
        )
    if selected in {"ALL", "RBD"} and "RBD_low_road_edge_count=" in json_summary:
        cues.append(
            "RBD_low_road_edge_count is present. Explicitly evaluate DEF-LD-RBD-FN and DEF-LD-RBD-RANGE for RBD before clearing RBD. A single road-edge output can still be a partial miss when the raw/QV frame shows both a left/right drivable boundary or a central divider plus road edge."
        )
    if not cues:
        return ["No compact JSON anomaly cue was detected; still scan every listed DEF-* issue type before assigning pass/fail."]
    cues.append("Do not summarize these cues away; mention the applicable DEF-* item in observed_evidence or inference.")
    return cues


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


def _render_candidate_evidence_packets(packets: list[dict[str, object]]) -> list[str]:
    if not packets:
        return ["- No candidate-specific packet generated for this package."]
    lines: list[str] = []
    for packet in packets:
        lines.extend(
            [
                f"### {packet['candidate_id']}",
                "",
                f"- feature: {packet['feature']}",
                f"- issue_type: {packet['issue_type']}",
                f"- object_ids: {packet['object_ids']}",
                f"- source: {packet['source']}",
                f"- packet_markdown: {packet['packet_markdown']}",
                f"- raw_frame_image: {packet['raw_frame_image']}",
                f"- qv_overlay_frame_image: {packet['qv_overlay_frame_image']}",
                f"- ics_crop_image: {packet['ics_crop_image']}",
                f"- ics_crop_status: {packet['ics_crop_status']}",
                f"- bev_crop_image: {packet['bev_crop_image']}",
                f"- bev_crop_status: {packet['bev_crop_status']}",
                f"- candidate_json_values: {packet['candidate_json_values']}",
                f"- candidate_review_summary: {packet.get('candidate_review_summary', '')}",
                "",
            ]
        )
    return lines


def _bullet_lines(values: object) -> list[str]:
    if not isinstance(values, list):
        return [f"- {values}"]
    return [f"- {value}" for value in values]
