"""Review task artifact generation for evidence packages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_vlm.models.evidence import FrameEvidencePackage
from auto_vlm.models.cases import normalize_review_features
from auto_vlm.vlm.candidates import obligations_from_json_summary
from auto_vlm.vlm.evidence_policy import strategies_for_issue_types, strategy_for_issue_type
from auto_vlm.vlm.feature_context import ACTIVE_FEATURES
from auto_vlm.vlm.reference_context import canonical_issue_type_ids, gtless_single_frame_applicability


def write_review_tasks(path: str | Path, packages: list[FrameEvidencePackage]) -> Path:
    """Write package/feature/candidate-level tasks needed before final reporting."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    tasks = build_review_tasks(packages)
    _write_feature_task_files(output.parent / "model" / "tasks", tasks)
    output.write_text(
        json.dumps(tasks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def build_review_tasks(packages: list[FrameEvidencePackage]) -> dict[str, Any]:
    tasks = [_package_task(package) for package in packages]
    candidate_count = sum(len(task["candidate_tasks"]) for task in tasks)
    feature_count = sum(len(task["feature_tasks"]) for task in tasks)
    return {
        "artifact_version": "review_tasks_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pending_review",
        "counts": {
            "packages": len(tasks),
            "feature_tasks": feature_count,
            "candidate_tasks": candidate_count,
        },
        "model_tasks_root": "model/tasks",
        "instructions": {
            "result_order": "raw_context first, then follow each issue_type's evidence_strategy order before decision",
            "final_report_rule": (
                "Do not generate result.xlsx or summary.html until llm_review_results.json "
                "passes review quality validation."
            ),
            "required_evidence_planes": [
                "raw_frame_image",
                "ics_crop_image",
                "bev_crop_image",
                "json_snippet_or_candidate_json_values",
            ],
            "json_rule": "JSON physical values support BEV overlay inspection; JSON must not replace BEV observation.",
            "plane_order_rule": (
                "Do not use one global raw->ICS->BEV order for every issue. Some geometry/range/heading/role "
                "issues are discovered in BEV/VCS first after raw context and then confirmed in ICS/QV."
            ),
        },
        "packages": tasks,
    }


def _package_task(package: FrameEvidencePackage) -> dict[str, Any]:
    selected_features = _selected_features(package.focus_feature)
    obligations = tuple(
        obligation
        for obligation in obligations_from_json_summary(package.json_summary)
        if any(feature.value == obligation.feature for feature in selected_features)
    )
    return {
        "package_id": package.package_id,
        "case_id": package.case_id,
        "sampled_frame": package.sampled_frame,
        "timestamp_sec": package.timestamp_sec,
        "focus_feature": package.focus_feature,
        "review_mode": package.review_mode,
        "evidence": {
            "raw_frame_image": _path_value(package.raw_frame_image),
            "json_snippet": _path_value(package.json_snippet),
            "json_summary": package.json_summary or "",
            "evidence_integrity": package.evidence_integrity.as_dict(),
        },
        "feature_tasks": [_feature_task(feature.value, package) for feature in selected_features],
        "candidate_tasks": [_candidate_task(package, obligation) for obligation in obligations],
    }


def _candidate_task(package: FrameEvidencePackage, obligation: Any) -> dict[str, Any]:
    evidence = {
        packet.candidate_id: packet.as_dict()
        for packet in package.candidate_evidence_packets
    }.get(obligation.candidate_id, {})
    return {
        "task_id": obligation.candidate_id,
        "feature": obligation.feature,
        "issue_type": obligation.issue_type,
        "object_ids": list(obligation.object_ids),
        "source": obligation.source,
        "evidence": evidence,
        "required_checked_planes": ["raw", "ics", "bev_vcs", "json"],
        "decision_options": ["issue", "cleared", "uncertain"],
        "required_observation_order": [
            "raw_observation",
            "ics_observation",
            "bev_observation",
            "json_observation",
            "decision",
        ],
        "required_reasoning_fields": [
            "raw_observation",
            "ics_observation",
            "bev_observation",
            "json_observation",
            "decision",
            "decision_reason",
            "uncertainty",
        ],
        "decision_rule": _candidate_decision_rule(obligation),
        "evidence_strategy": strategy_for_issue_type(obligation.issue_type).as_dict(),
    }


def _feature_task(feature: str, package: FrameEvidencePackage) -> dict[str, Any]:
    feature_enum = next(item for item in ACTIVE_FEATURES if item.value == feature)
    applicability = gtless_single_frame_applicability(feature_enum)
    evaluated_issue_types = [
        issue_id
        for issue_id in canonical_issue_type_ids(feature_enum)
        if applicability[issue_id] != "not_evaluable"
    ]
    return {
        "task_id": f"{package.package_id}::{feature}",
        "package_id": package.package_id,
        "case_id": package.case_id,
        "sampled_frame": package.sampled_frame,
        "feature": feature,
        "evidence": _feature_evidence(package, feature),
        "required_result_values": ["pass", "fail"],
        "issue_types": evaluated_issue_types,
        "evaluated_issue_types": evaluated_issue_types,
        "candidate_hints": _candidate_hints(package, feature),
        "required_schema": {
            "package_id": "string",
            "feature": feature,
            "result": "pass|fail",
            "confidence": "high|medium|low",
            "evaluated_issue_types": "list[DEF-*]",
            "triggered_issue_types": "list[DEF-*]",
            "summary": "string",
            "observed_evidence": "string citing raw, ICS/QV, BEV/VCS, and JSON",
            "inference": "string",
            "uncertainty": "string",
            "candidate_adjudications": "list[object], optional",
        },
        "issue_evidence_strategy": [
            strategy.as_dict()
            for strategy in strategies_for_issue_types(evaluated_issue_types)
        ],
        "required_reasoning_fields": [
            "summary",
            "observed_evidence",
            "inference",
            "uncertainty",
        ],
        "required_observed_evidence": [
            "raw frame observation",
            "ICS/QV overlay observation",
            "BEV/world-space observation",
            "concrete JSON summary key/value",
        ],
    }


def _selected_features(focus_feature: str) -> tuple[Any, ...]:
    normalized = normalize_review_features(focus_feature)
    if normalized == "ALL":
        return ACTIVE_FEATURES
    return tuple(feature for feature in ACTIVE_FEATURES if feature.value in normalized.split(","))


def _candidate_hints(package: FrameEvidencePackage, feature: str) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for obligation in obligations_from_json_summary(package.json_summary):
        if obligation.feature == feature:
            hints.append(_candidate_task(package, obligation))
    return hints


def _write_feature_task_files(root: Path, tasks: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for package_task in tasks["packages"]:
        package_id = package_task["package_id"]
        package_dir = root / package_id
        package_dir.mkdir(parents=True, exist_ok=True)
        for task in package_task["feature_tasks"]:
            task_path = package_dir / f"{task['feature']}.json"
            task_path.write_text(
                json.dumps(task, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )


def _feature_evidence(package: FrameEvidencePackage, feature: str) -> dict[str, Any]:
    for packet in package.feature_evidence_packets:
        if packet.feature == feature:
            return packet.as_dict()
    return {
        "raw_frame_image": _path_value(package.raw_frame_image),
        "ics_crop_image": "",
        "ics_crop_status": "unavailable_or_unverified",
        "bev_crop_image": "",
        "bev_crop_status": "unavailable_or_unverified",
        "json_snippet": _path_value(package.json_snippet),
        "json_summary": package.json_summary or "",
        "packet_markdown": "",
    }


def _path_value(path: Path | None) -> str:
    return str(path) if path else ""


def _candidate_decision_rule(obligation: Any) -> str:
    if obligation.issue_type == "DEF-OD-BBOX-DUP":
        return (
            "For DEF-OD-BBOX-DUP, issue only when raw/ICS and BEV overlay both support "
            "same-object duplicate; clear when BEV overlay separates them; mark uncertain "
            "when BEV overlay is unreadable or unavailable. JSON supports BEV and cannot replace it."
        )
    if obligation.issue_type == "DEF-OD-BBOX-FIT":
        return (
            "For DEF-OD-BBOX-FIT, OD_large_bbox_candidates is a required review cue. "
            "Issue when raw object shape and ICS/QV bbox fit show an oversized, shifted, "
            "or badly fitted box; clear only with explicit raw, ICS/QV, BEV, and JSON evidence."
        )
    if obligation.issue_type == "DEF-LD-RBD-FN":
        return (
            "For DEF-LD-RBD-FN, RBD_low_road_edge_count is a required review cue. "
            "Issue when visible road edges or boundaries in raw/ICS are missing or under-covered "
            "in QV/BEV/JSON for the sampled frame."
        )
    return "Review raw, ICS/QV, BEV/VCS, and JSON evidence before deciding issue, cleared, or uncertain."
