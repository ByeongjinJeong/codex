from __future__ import annotations

from auto_vlm.models.results import Confidence, FeatureReviewResult, FrameTestResult, PackageReviewResult
from auto_vlm.vlm.cross_feature_audit import audit_package_result


def test_cross_feature_audit_requests_rerun_when_pass_reasoning_claims_issue():
    result = PackageReviewResult(
        feature_results=(
            FeatureReviewResult(
                feature="OD",
                result=FrameTestResult.PASS,
                confidence=Confidence.MEDIUM,
                summary="OD has an issue in the overlay",
                observed_evidence="raw/qv/bev/json",
                inference="issue is visible",
            ),
        )
    )

    audit = audit_package_result("CASE_001__frame_00000100", result)

    assert audit["status"] == "rerun_required"
    assert audit["findings"][0]["code"] == "pass_reasoning_claims_issue"


def test_cross_feature_audit_flags_duplicate_issue_ownership():
    result = PackageReviewResult(
        feature_results=(
            FeatureReviewResult(
                feature="LD",
                result=FrameTestResult.FAIL,
                confidence=Confidence.HIGH,
                triggered_issue_types=("DEF-LD-RBD-FN",),
            ),
            FeatureReviewResult(
                feature="RBD",
                result=FrameTestResult.FAIL,
                confidence=Confidence.HIGH,
                triggered_issue_types=("DEF-LD-RBD-FN",),
            ),
        )
    )

    audit = audit_package_result("CASE_001__frame_00000100", result)

    assert audit["status"] == "conflict"
    assert audit["findings"][0]["code"] == "duplicate_issue_ownership"
