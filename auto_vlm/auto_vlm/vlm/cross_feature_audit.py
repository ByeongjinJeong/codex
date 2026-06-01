"""Lightweight deterministic cross-feature audit for package results."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_vlm.models.results import FrameTestResult, PackageReviewResult


@dataclass(frozen=True)
class CrossFeatureAuditSummary:
    accepted: int = 0
    rerun_required: int = 0
    conflicts: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "accepted": self.accepted,
            "rerun_required": self.rerun_required,
            "conflicts": self.conflicts,
        }


def write_cross_feature_audits(
    root: str | Path,
    results: dict[str, PackageReviewResult],
) -> CrossFeatureAuditSummary:
    audit_root = Path(root)
    audit_root.mkdir(parents=True, exist_ok=True)
    accepted = 0
    rerun_required = 0
    conflicts = 0
    for package_id, result in sorted(results.items()):
        audit = audit_package_result(package_id, result)
        status = audit["status"]
        if status == "accepted":
            accepted += 1
        elif status == "rerun_required":
            rerun_required += 1
        else:
            conflicts += 1
        (audit_root / f"{package_id}.json").write_text(
            json.dumps(audit, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return CrossFeatureAuditSummary(
        accepted=accepted,
        rerun_required=rerun_required,
        conflicts=conflicts,
    )


def audit_package_result(package_id: str, result: PackageReviewResult) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    issue_owners: dict[str, list[str]] = defaultdict(list)
    for feature in result.feature_results:
        text = " ".join([feature.summary, feature.observed_evidence, feature.inference]).lower()
        if feature.result == FrameTestResult.PASS and _claims_issue(text):
            findings.append(
                {
                    "code": "pass_reasoning_claims_issue",
                    "feature": feature.feature,
                    "action": "rerun_feature",
                    "message": "Feature is PASS while reasoning says an issue exists.",
                }
            )
        if feature.result == FrameTestResult.FAIL and not feature.triggered_issue_types:
            findings.append(
                {
                    "code": "fail_without_triggered_issue",
                    "feature": feature.feature,
                    "action": "rerun_feature",
                    "message": "Feature is FAIL without triggered_issue_types.",
                }
            )
        for issue_type in feature.triggered_issue_types:
            issue_owners[issue_type].append(feature.feature)

    for issue_type, owners in sorted(issue_owners.items()):
        unique_owners = sorted(set(owners))
        if len(unique_owners) > 1:
            findings.append(
                {
                    "code": "duplicate_issue_ownership",
                    "feature": ",".join(unique_owners),
                    "action": "resolve_conflict",
                    "message": f"{issue_type} is triggered by multiple features.",
                }
            )

    if any(finding["action"] == "resolve_conflict" for finding in findings):
        status = "conflict"
    elif findings:
        status = "rerun_required"
    else:
        status = "accepted"
    return {
        "package_id": package_id,
        "status": status,
        "findings": findings,
    }


def _claims_issue(text: str) -> bool:
    markers = (" issue", "fail", "fails", "결함", "이슈", "오류", "문제")
    negations = ("no issue", "not an issue", "이슈 없음", "문제 없음", "확인되지")
    return any(marker in text for marker in markers) and not any(marker in text for marker in negations)
