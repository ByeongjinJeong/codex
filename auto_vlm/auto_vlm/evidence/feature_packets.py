"""Feature-level review packet generation."""

from __future__ import annotations

from pathlib import Path

from auto_vlm.models.evidence import FeatureEvidencePacket, FrameEvidencePackage
from auto_vlm.evidence.overlay_regions import write_full_bev_region, write_full_ics_region
from auto_vlm.models.vlm import Feature
from auto_vlm.vlm.feature_context import ACTIVE_FEATURES
from auto_vlm.vlm.evidence_policy import strategies_for_issue_types
from auto_vlm.vlm.reference_context import canonical_issue_type_ids, gtless_single_frame_applicability


def write_feature_evidence_packets(
    package: FrameEvidencePackage,
    case_dir: str | Path,
) -> tuple[FeatureEvidencePacket, ...]:
    """Write one concise, comprehensive review packet per active feature."""
    root = Path(case_dir)
    packet_dir = root / "feature_packets" / package.package_id
    evidence_dir = root / "feature_evidence" / package.package_id
    packet_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    selected = _selected_features(package.focus_feature)
    packets: list[FeatureEvidencePacket] = []
    for feature in selected:
        issue_types = _evaluated_issue_types(feature)
        qv_overlay = package.qv_overlay_frame_image or package.center_frame_image
        ics_crop, ics_status = write_full_ics_region(package, qv_overlay, evidence_dir / f"{feature.value}__ics.jpg")
        bev_crop, bev_status = write_full_bev_region(package, qv_overlay, evidence_dir / f"{feature.value}__bev.jpg")
        packet = FeatureEvidencePacket(
            package_id=package.package_id,
            feature=feature.value,
            raw_frame_image=package.raw_frame_image,
            qv_overlay_frame_image=qv_overlay,
            ics_crop_image=ics_crop,
            ics_crop_status=ics_status,
            bev_crop_image=bev_crop,
            bev_crop_status=bev_status,
            json_snippet=package.json_snippet,
            json_summary=package.json_summary or "",
            evaluation_scope=_feature_scope(package, feature.value),
            evaluated_issue_types=issue_types,
            packet_markdown=packet_dir / f"{feature.value}.md",
        )
        packet.packet_markdown.write_text(_render_feature_packet(packet), encoding="utf-8")
        packets.append(packet)
    return tuple(packets)


def _selected_features(focus_feature: str) -> tuple[Feature, ...]:
    # Workbook final reports require OD/LD/RBD/TS/TL rows for every package.
    # Even when input focus_feature narrows JSON summarization, evidence packets
    # must still exist for all active review features so raw/ICS/BEV/JSON checks
    # cannot be skipped in the final review.
    Feature(focus_feature)
    return ACTIVE_FEATURES


def _evaluated_issue_types(feature: Feature) -> tuple[str, ...]:
    applicability = gtless_single_frame_applicability(feature)
    return tuple(
        issue_id
        for issue_id in canonical_issue_type_ids(feature)
        if applicability[issue_id] != "not_evaluable"
    )


def _render_feature_packet(packet: FeatureEvidencePacket) -> str:
    return "\n".join(
        [
            f"# Feature Review Packet: {packet.package_id}::{packet.feature}",
            "",
            "This packet is for a full feature sweep.",
            "",
            "## Evidence",
            "",
            f"- raw_frame_image: {_path_value(packet.raw_frame_image)}",
            f"- ics_crop_image: {_path_value(packet.ics_crop_image)}",
            f"- ics_crop_status: {packet.ics_crop_status}",
            f"- bev_crop_image: {_path_value(packet.bev_crop_image)}",
            f"- bev_crop_status: {packet.bev_crop_status}",
            f"- json_snippet: {_path_value(packet.json_snippet)}",
            f"- json_summary: {packet.json_summary}",
            "",
            *_scope_lines(packet),
            "",
            "## Required Review Order",
            "",
            "1. Raw context first: identify the driving environment and visible objects, lanes, road edges, signs, lights, and conditions relevant to this feature.",
            "2. Then follow the issue-specific evidence strategy below. Some issues are BEV/VCS-first after raw context and must be checked in BEV before ICS confirmation.",
            "3. JSON support: use SW output values only as supporting evidence for what raw/ICS/BEV show.",
            "4. Evaluation scope: use scope annotations only to decide whether an observed issue is reportable. Scope annotations are not evidence that an issue exists.",
            "5. Issue-type sweep: evaluate every listed DEF-* item before pass/fail.",
            "",
            "JSON is SW output evidence, not ground truth. It must not replace visual raw/ICS/BEV inspection.",
            "Do not assume ICS is the primary discovery plane for every issue. For geometry/range/heading/role/coefficient issues, BEV/VCS may expose the issue before ICS can confirm projection consistency.",
            "Write summaries in Korean. When reporting an issue, describe the raw-video scenario or driving environment first, then name the observed issue type.",
            "Example style: '전방 좌측 도로의 긴 트럭을 중복 검출하여 OD-BBOX-DUP 이슈 관찰'.",
            "",
            "## Issue Evidence Strategy",
            "",
            *_strategy_lines(packet.evaluated_issue_types),
            "",
            "## Issue Types To Sweep",
            "",
            *_bullet_lines(packet.evaluated_issue_types),
            "",
            "## Required Output Fields",
            "",
            "```text",
            "feature:",
            "result: pass | fail",
            "confidence: high | medium | low",
            "evaluated_issue_types:",
            "triggered_issue_types:",
            "summary: 한글로 작성. raw 영상 시나리오/현재 환경을 먼저 설명하고 관찰된 이슈 타입을 함께 적기",
            "observed_evidence: cite raw, ICS/QV overlay, BEV/world-space when visible, and JSON support",
            "inference:",
            "uncertainty:",
            "```",
            "",
        ]
    )


def _bullet_lines(values: tuple[str, ...]) -> list[str]:
    if not values:
        return ["- No GT-less evaluable issue types configured for this feature."]
    return [f"- {value}" for value in values]


def _strategy_lines(issue_types: tuple[str, ...]) -> list[str]:
    if not issue_types:
        return ["- No issue-specific evidence strategy configured for this feature."]
    lines: list[str] = []
    for strategy in strategies_for_issue_types(issue_types):
        lines.append(f"- {strategy.as_text()}")
        for item in strategy.must_not:
            lines.append(f"  must_not: {item}")
    return lines


def _feature_scope(package: FrameEvidencePackage, feature: str) -> dict:
    features = package.evaluation_scope.get("features")
    if not isinstance(features, dict):
        return {}
    value = features.get(feature)
    return value if isinstance(value, dict) else {}


def _scope_lines(packet: FeatureEvidencePacket) -> list[str]:
    if packet.feature != "OD" or not packet.evaluation_scope:
        return []
    scope = packet.evaluation_scope
    rules = scope.get("rules", {})
    summary = scope.get("summary", {})
    objects = scope.get("objects", [])
    lines = [
        "## Evaluation Scope",
        "",
        "OD scope annotations are range filters for reportability, not issue evidence.",
        "Do not use scope annotations to decide that an issue exists.",
        f"- rules: {rules}",
        f"- summary: {summary}",
    ]
    if isinstance(objects, list) and objects:
        lines.append("- objects:")
        for item in objects[:20]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "  - "
                f"object_id={item.get('object_id', '')}; "
                f"class={item.get('class', '')}; "
                f"category={item.get('category', '')}; "
                f"long_distance_m={item.get('long_distance_m', '')}; "
                f"scope={item.get('scope', '')}; "
                f"reason={item.get('reason', '')}"
            )
    else:
        lines.append("- objects: none or unavailable")
    lines.extend(
        [
            "- If raw evidence contradicts JSON class or distance, treat scope as uncertain.",
            "- Out-of-scope observations should not become final fail results unless scope is uncertain or contradicted by raw evidence.",
        ]
    )
    return lines


def _path_value(path: Path | None) -> str:
    return str(path) if path else ""
