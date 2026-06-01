"""Candidate-specific evidence packet generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from auto_vlm.evidence.overlay_regions import write_full_bev_region, write_full_ics_region, write_object_ics_region
from auto_vlm.models.cases import normalize_review_features
from auto_vlm.models.evidence import CandidateEvidencePacket, FrameEvidencePackage
from auto_vlm.vlm.candidates import ReviewCandidateObligation, obligations_from_json_summary
from auto_vlm.vlm.evidence_policy import strategy_for_issue_type


def write_candidate_evidence_packets(
    package: FrameEvidencePackage,
    case_dir: str | Path,
) -> tuple[CandidateEvidencePacket, ...]:
    """Write focused evidence artifacts for machine-detected review candidates."""
    selected_features = _selected_focus_features(package.focus_feature)
    obligations = tuple(
        obligation
        for obligation in obligations_from_json_summary(package.json_summary)
        if obligation.feature in selected_features
    )
    if not obligations:
        return ()

    root = Path(case_dir)
    evidence_dir = root / "candidate_evidence" / package.package_id
    packet_dir = root / "candidate_packets" / package.package_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packet_dir.mkdir(parents=True, exist_ok=True)

    json_data = _load_json(package.json_snippet)
    packets: list[CandidateEvidencePacket] = []
    for obligation in obligations:
        object_json = _candidate_object_json(json_data, obligation.object_ids)
        bev_analysis = _bev_extent_analysis(object_json)
        review_hint = _candidate_review_hint(obligation, object_json, bev_analysis)
        review_summary = _candidate_review_summary(obligation, bev_analysis)
        json_path = evidence_dir / f"{obligation.candidate_id}__json.json"
        json_path.write_text(
            json.dumps(
                {
                    "candidate_id": obligation.candidate_id,
                    "package_id": package.package_id,
                    "issue_type": obligation.issue_type,
                    "object_ids": list(obligation.object_ids),
                    "source": obligation.source,
                    "objects": object_json,
                    "bev_extent_analysis": bev_analysis,
                    "candidate_review_hint": review_hint,
                    "json_summary": package.json_summary or "",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        ics_crop, ics_status = write_object_ics_region(
            package,
            package.qv_overlay_frame_image or package.center_frame_image,
            object_json,
            evidence_dir / f"{obligation.candidate_id}__ics.jpg",
        )
        if ics_crop is None:
            ics_crop, ics_status = write_full_ics_region(
                package,
                package.qv_overlay_frame_image or package.center_frame_image,
                evidence_dir / f"{obligation.candidate_id}__ics.jpg",
            )
        bev_crop, bev_status = write_full_bev_region(
            package,
            package.qv_overlay_frame_image or package.center_frame_image,
            evidence_dir / f"{obligation.candidate_id}__bev.jpg",
        )
        packet = CandidateEvidencePacket(
            candidate_id=obligation.candidate_id,
            package_id=package.package_id,
            feature=obligation.feature,
            issue_type=obligation.issue_type,
            object_ids=obligation.object_ids,
            source=obligation.source,
            raw_frame_image=package.raw_frame_image,
            qv_overlay_frame_image=package.qv_overlay_frame_image or package.center_frame_image,
            ics_crop_image=ics_crop,
            ics_crop_status=ics_status,
            bev_crop_image=bev_crop,
            bev_crop_status=bev_status,
            candidate_json_values=json_path,
            full_json_snippet=package.json_snippet,
            json_summary=package.json_summary or "",
            candidate_review_summary=review_summary,
            packet_markdown=packet_dir / f"{obligation.candidate_id}.md",
        )
        packet.packet_markdown.write_text(_render_candidate_packet(packet), encoding="utf-8")
        packets.append(packet)
    return tuple(packets)


def _selected_focus_features(focus_feature: str) -> set[str]:
    normalized = normalize_review_features(focus_feature)
    if normalized == "ALL":
        return {"OD", "LD", "RBD", "TS", "TL"}
    return set(normalized.split(","))


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _candidate_object_json(data: dict[str, Any], object_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    objects = _qv_objects(data)
    wanted = {str(object_id) for object_id in object_ids}
    return [obj for obj in objects if str(obj.get("VIS_OBJ_ID")) in wanted]


def _qv_objects(data: dict[str, Any]) -> list[dict[str, Any]]:
    section = data.get("avi_objects")
    if not isinstance(section, dict):
        return []
    objects = section.get("VIS_OBJ_Element")
    if not isinstance(objects, list):
        return []
    return [item for item in objects if isinstance(item, dict)]


def _bev_extent_analysis(objects: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize BEV physical extents for duplicate-object review."""
    if len(objects) != 2:
        return {
            "status": "unavailable_expected_two_objects",
            "objects": len(objects),
            "object_extents": [
                extent for obj in objects if (extent := _bev_object_extent(obj)) is not None
            ],
        }

    left = _bev_object_extent(objects[0])
    right = _bev_object_extent(objects[1])
    if left is None or right is None:
        return {"status": "unavailable_missing_physical_state"}

    delta_long = abs(left["long_distance"] - right["long_distance"])
    delta_lat = abs(left["lat_distance"] - right["lat_distance"])
    long_overlap = _interval_overlap(left["long_extent"], right["long_extent"])
    lat_overlap = _interval_overlap(left["lat_extent"], right["lat_extent"])
    return {
        "status": "available",
        "object_extents": [left, right],
        "delta_long": delta_long,
        "delta_lat": delta_lat,
        "longitudinal_extent_overlap": long_overlap,
        "lateral_extent_overlap": lat_overlap,
        "extent_overlap_hint": long_overlap > 0 and lat_overlap > 0,
    }


def _bev_object_extent(obj: dict[str, Any]) -> dict[str, Any] | None:
    physical = obj.get("VIS_OBJ_Physical_State")
    if not isinstance(physical, dict):
        return None

    long_distance = _number(physical.get("Long_Distance"))
    lat_distance = _number(physical.get("Lat_Distance"))
    length = _number(physical.get("Length"))
    width = _number(physical.get("Width"))
    if long_distance is None or lat_distance is None or length is None or width is None:
        return None

    half_length = max(0.0, length) / 2.0
    half_width = max(0.0, width) / 2.0
    return {
        "object_id": str(obj.get("VIS_OBJ_ID")),
        "long_distance": long_distance,
        "lat_distance": lat_distance,
        "length": length,
        "width": width,
        "long_extent": [long_distance - half_length, long_distance + half_length],
        "lat_extent": [lat_distance - half_width, lat_distance + half_width],
    }


def _number(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def _interval_overlap(left: list[float], right: list[float]) -> float:
    return max(0.0, min(left[1], right[1]) - max(left[0], right[0]))


def _candidate_review_hint(
    obligation: ReviewCandidateObligation,
    objects: list[dict[str, Any]],
    bev_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Return issue-type-specific cues so reviewers do not apply DUP rules to every candidate."""
    if obligation.issue_type == "DEF-OD-BBOX-DUP":
        return {
            "decision_rule": (
                "Issue when raw/ICS and BEV/VCS both support the same physical object being "
                "represented by multiple OD boxes. Clear only when BEV/VCS clearly separates them."
            ),
            "primary_json_keys": ["bev_extent_analysis", "OD_bbox_overlap_candidates"],
            "bev_precheck": _od_dup_bev_precheck(bev_analysis),
            "evidence_strategy": strategy_for_issue_type(obligation.issue_type).as_dict(),
        }
    if obligation.issue_type == "DEF-OD-BBOX-FIT":
        extent = _bev_object_extent(objects[0]) if objects else None
        return {
            "decision_rule": (
                "Large image coverage is a required review cue, not automatic proof. Issue when "
                "raw/QV bbox coverage is implausibly oversized for the visible object; do not clear "
                "only because the object is near-field or large."
            ),
            "primary_json_keys": ["OD_large_bbox_candidates"],
            "object_extent": extent,
            "evidence_strategy": strategy_for_issue_type(obligation.issue_type).as_dict(),
        }
    if obligation.issue_type == "DEF-LD-RBD-FN":
        return {
            "decision_rule": (
                "Issue when raw roadway boundaries are visible but QV/BEV/JSON road-edge coverage "
                "is below expected minimum for the sampled frame."
            ),
            "primary_json_keys": ["RBD_low_road_edge_count", "road_edges"],
            "evidence_strategy": strategy_for_issue_type(obligation.issue_type).as_dict(),
        }
    return {
        "decision_rule": "Review raw, ICS/QV, BEV/VCS, and JSON evidence before deciding.",
        "primary_json_keys": [obligation.source],
        "evidence_strategy": strategy_for_issue_type(obligation.issue_type).as_dict(),
    }


def _od_dup_bev_precheck(bev_analysis: dict[str, Any]) -> dict[str, Any]:
    if bev_analysis.get("status") != "available":
        return {
            "recommended_decision": "uncertain",
            "reason": "BEV physical extents are unavailable; visual BEV inspection is required.",
        }
    if bev_analysis.get("extent_overlap_hint") is False:
        return {
            "recommended_decision": "cleared",
            "reason": (
                "BEV physical extents do not overlap in both axes; this is not a confirmed "
                "same-object duplicate."
            ),
            "delta_long": bev_analysis.get("delta_long"),
            "delta_lat": bev_analysis.get("delta_lat"),
            "longitudinal_extent_overlap": bev_analysis.get("longitudinal_extent_overlap"),
            "lateral_extent_overlap": bev_analysis.get("lateral_extent_overlap"),
        }
    return {
        "recommended_decision": "review_required_possible_issue",
        "reason": (
            "BEV physical extents overlap in both axes. This is a strong cue, but raw/ICS "
            "still must confirm the same physical object before marking issue."
        ),
        "delta_long": bev_analysis.get("delta_long"),
        "delta_lat": bev_analysis.get("delta_lat"),
        "longitudinal_extent_overlap": bev_analysis.get("longitudinal_extent_overlap"),
        "lateral_extent_overlap": bev_analysis.get("lateral_extent_overlap"),
    }


def _candidate_review_summary(
    obligation: ReviewCandidateObligation,
    bev_analysis: dict[str, Any],
) -> str:
    if obligation.issue_type != "DEF-OD-BBOX-DUP":
        return ""
    precheck = _od_dup_bev_precheck(bev_analysis)
    if precheck["recommended_decision"] == "cleared":
        return (
            "BEV_PRECHECK=cleared; "
            f"delta_long={_fmt(precheck.get('delta_long'))}m; "
            f"delta_lat={_fmt(precheck.get('delta_lat'))}m; "
            f"longitudinal_extent_overlap={_fmt(precheck.get('longitudinal_extent_overlap'))}; "
            f"lateral_extent_overlap={_fmt(precheck.get('lateral_extent_overlap'))}; "
            "BEV separates the objects, so DEF-OD-BBOX-DUP must be cleared unless raw/ICS/BEV "
            "evidence contradicts this precheck."
        )
    if precheck["recommended_decision"] == "review_required_possible_issue":
        return (
            "BEV_PRECHECK=possible_issue_requires_visual_confirmation; "
            f"delta_long={_fmt(precheck.get('delta_long'))}m; "
            f"delta_lat={_fmt(precheck.get('delta_lat'))}m; "
            f"longitudinal_extent_overlap={_fmt(precheck.get('longitudinal_extent_overlap'))}; "
            f"lateral_extent_overlap={_fmt(precheck.get('lateral_extent_overlap'))}; "
            "raw/ICS must still confirm same physical object before marking DEF-OD-BBOX-DUP issue."
        )
    return "BEV_PRECHECK=uncertain; BEV physical extents are unavailable and visual BEV inspection is required."


def _fmt(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.3f}"
    return "n/a"


def _render_candidate_packet(packet: CandidateEvidencePacket) -> str:
    return "\n".join(
        [
            f"# Candidate Evidence Packet: {packet.candidate_id}",
            "",
            "## Candidate",
            "",
            f"- package_id: {packet.package_id}",
            f"- issue_type: {packet.issue_type}",
            f"- feature: {packet.feature}",
            f"- object_ids: {', '.join(packet.object_ids)}",
            f"- source: {packet.source}",
            "",
            "## Evidence",
            "",
            f"- raw_frame_image: {_path_value(packet.raw_frame_image)}",
            f"- ics_crop_image: {_path_value(packet.ics_crop_image)}",
            f"- ics_crop_status: {packet.ics_crop_status}",
            f"- bev_crop_image: {_path_value(packet.bev_crop_image)}",
            f"- bev_crop_status: {packet.bev_crop_status}",
            f"- candidate_json_values: {_path_value(packet.candidate_json_values)}",
            f"- full_json_snippet: {_path_value(packet.full_json_snippet)}",
            f"- candidate_review_summary: {packet.candidate_review_summary}",
            f"- json_summary: {packet.json_summary}",
            "",
            "## Required Tester Order",
            "",
            f"- evidence_strategy: {strategy_for_issue_type(packet.issue_type).as_text()}",
            "1. Raw observation / raw context: describe the real scene and relevant target semantics.",
            "2. Follow the evidence_strategy order for this issue type. Do not assume ICS must always come before BEV.",
            "3. JSON support check: use candidate_json_values only to support visual raw/ICS/BEV evidence. For OD bbox duplicate candidates, check bev_extent_analysis, not only center distance.",
            "4. Decision: issue, cleared, or uncertain.",
            "",
            "JSON physical values support the BEV overlay observation. They must not replace BEV overlay inspection.",
            *_candidate_rule_lines(packet),
            "Write the summary and decision_reason in Korean. Start from the raw-video scene or road environment, then state the observed issue type.",
            "",
            "## Required Output Fields",
            "",
            "```text",
            "candidate_id:",
            "feature:",
            "issue_type:",
            "object_ids:",
            "raw_observation:",
            "ics_observation:",
            "bev_observation:",
            "json_observation:",
            "decision: issue | cleared | uncertain",
            "decision_reason:",
            "uncertainty:",
            "```",
            "",
        ]
    )


def _path_value(path: Path | None) -> str:
    return str(path) if path else ""


def _candidate_rule_lines(packet: CandidateEvidencePacket) -> list[str]:
    if packet.issue_type == "DEF-OD-BBOX-DUP":
        return [
            "For OD bbox duplicate candidates, Long_Distance/Lat_Distance center distance alone is insufficient; compare Length/Width extents and lateral alignment.",
            "For DEF-OD-BBOX-DUP, mark issue only when raw/ICS and BEV overlay both support same-object duplicate.",
            "Clear when BEV overlay clearly separates the objects. Mark uncertain when BEV overlay is unreadable or unavailable.",
        ]
    if packet.issue_type == "DEF-OD-BBOX-FIT":
        return [
            "For DEF-OD-BBOX-FIT, large image coverage is a required review cue, never automatic proof.",
            "Mark issue when the QV bbox is visibly too large, too small, shifted, or poorly fitted relative to the raw object.",
            "Do not clear only because the object is near-field or large; explicitly cite raw shape, ICS bbox fit, BEV placement, and JSON OD_large_bbox_candidates.",
        ]
    if packet.issue_type == "DEF-LD-RBD-FN":
        return [
            "For DEF-LD-RBD-FN, compare visible roadway edges in raw/ICS against BEV road-edge coverage and JSON road_edges/RBD_low_road_edge_count.",
            "Mark issue when a visible road edge or boundary is missing or under-covered in QV/BEV for the sampled frame.",
        ]
    return ["Apply the candidate issue definition named above and cite all evidence planes."]
