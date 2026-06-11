"""Review task artifact generation for evidence packages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_vlm.models.evidence import FrameEvidencePackage
from auto_vlm.vlm.evidence_policy import strategies_for_issue_types
from auto_vlm.vlm.feature_context import ACTIVE_FEATURES
from auto_vlm.vlm.reference_context import canonical_issue_type_ids, gtless_single_frame_applicability


def write_review_tasks(path: str | Path, packages: list[FrameEvidencePackage]) -> Path:
    """Write package and feature-level tasks needed before final reporting."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_review_tasks(packages), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


def build_review_tasks(packages: list[FrameEvidencePackage]) -> dict[str, Any]:
    tasks = [_package_task(package) for package in packages]
    feature_count = sum(len(task["feature_tasks"]) for task in tasks)
    return {
        "artifact_version": "review_tasks_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pending_review",
        "counts": {
            "packages": len(tasks),
            "feature_tasks": feature_count,
        },
        "instructions": {
            "result_order": "raw_context first, then follow each issue_type's evidence_strategy order before decision",
            "final_report_rule": (
                "After evidence/task generation, continue through the available review, "
                "validation, and report stages. Partial evidence output is incomplete."
            ),
            "required_evidence_planes": [
                "raw_frame_image",
                "ics_crop_image",
                "bev_crop_image",
                "json_snippet",
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
            "evaluation_scope": package.evaluation_scope,
            "evidence_integrity": package.evidence_integrity.as_dict(),
        },
        "feature_tasks": [_feature_task(feature.value, package) for feature in ACTIVE_FEATURES],
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
        "feature": feature,
        "evidence": _feature_evidence(package, feature),
        "required_result_values": ["pass", "fail"],
        "evaluated_issue_types": evaluated_issue_types,
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
        "evaluation_scope_rule": (
            "For OD, use evaluation_scope only to decide whether an observed issue is reportable. "
            "Do not use scope annotations as evidence that an issue exists."
        ) if feature == "OD" else "",
    }


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
