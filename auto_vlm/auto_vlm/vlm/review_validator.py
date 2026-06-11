"""Quality gate for loaded review results before final report generation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from auto_vlm.models.evidence import FrameEvidencePackage
from auto_vlm.models.results import ACTIVE_REVIEW_FEATURES, PackageReviewResult


MOJIBAKE_MARKERS = ("À", "Á", "¿", "Ã", "½", "¾", "¹", "º", "Ä", "Ç")
JSON_EVIDENCE_MARKERS = (
    "objects=",
    "lanes=",
    "road_edges=",
    "signs=",
    "lights=",
)


@dataclass(frozen=True)
class ReviewQualityFinding:
    code: str
    severity: str
    package_id: str = ""
    feature: str = ""
    message: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "package_id": self.package_id,
            "feature": self.feature,
            "message": self.message,
        }


@dataclass(frozen=True)
class ReviewQualityReport:
    status: str
    findings: tuple[ReviewQualityFinding, ...] = ()

    @property
    def errors(self) -> tuple[ReviewQualityFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "error")

    @property
    def warnings(self) -> tuple[ReviewQualityFinding, ...]:
        return tuple(finding for finding in self.findings if finding.severity == "warning")

    @property
    def can_generate_final_report(self) -> bool:
        return self.status == "passed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "findings": [finding.as_dict() for finding in self.findings],
        }


def empty_review_quality_report() -> ReviewQualityReport:
    return ReviewQualityReport(status="not_run")


def validate_review_quality(
    packages: list[FrameEvidencePackage],
    results: dict[str, PackageReviewResult],
) -> ReviewQualityReport:
    """Return whether loaded review results are safe to promote to final reports.

    This does not decide whether the model judgment is correct. It only blocks
    review artifacts that are structurally suspicious enough that final report
    generation would create false confidence.
    """
    if not results:
        return empty_review_quality_report()

    findings: list[ReviewQualityFinding] = []
    packages_by_id = {package.package_id: package for package in packages}
    result_ids = set(results)
    package_ids = set(packages_by_id)

    for package_id in sorted(package_ids - result_ids):
        findings.append(
            ReviewQualityFinding(
                code="missing_review_result",
                severity="error",
                package_id=package_id,
                message="Package has no loaded review result.",
            )
        )
    for package_id in sorted(result_ids - package_ids):
        findings.append(
            ReviewQualityFinding(
                code="unknown_review_result",
                severity="error",
                package_id=package_id,
                message="Review result does not match a generated package.",
            )
        )

    summary_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for package in packages:
        result = results.get(package.package_id)
        if result is None:
            continue

        features = {feature.feature: feature for feature in result.feature_results}
        missing_features = sorted(ACTIVE_REVIEW_FEATURES - set(features))
        for feature in missing_features:
            findings.append(
                ReviewQualityFinding(
                    code="missing_feature_review",
                    severity="error",
                    package_id=package.package_id,
                    feature=feature,
                    message="Full review mode requires OD, LD, RBD, TS, and TL feature rows.",
                )
            )

        for feature_name, feature in features.items():
            summary_counts[feature_name][feature.summary.strip()] += 1
            _validate_text_encoding(findings, package.package_id, feature_name, feature.summary, "summary")
            _validate_text_encoding(
                findings,
                package.package_id,
                feature_name,
                feature.observed_evidence,
                "observed_evidence",
            )
            _validate_text_encoding(findings, package.package_id, feature_name, feature.inference, "inference")
            _validate_evidence_specificity(findings, package, feature_name, feature.observed_evidence)

    for feature_name, counter in summary_counts.items():
        for summary, count in counter.items():
            if count >= 3 and _looks_like_template_summary(summary):
                findings.append(
                    ReviewQualityFinding(
                        code="repeated_template_summary",
                        severity="error",
                        feature=feature_name,
                        message=(
                            f"{feature_name} summary is repeated across {count} packages; "
                            "review looks templated rather than package-specific."
                        ),
                    )
                )

    status = "failed" if any(finding.severity == "error" for finding in findings) else "passed"
    return ReviewQualityReport(status=status, findings=tuple(findings))


def _validate_text_encoding(
    findings: list[ReviewQualityFinding],
    package_id: str,
    feature: str,
    text: str,
    field_name: str,
) -> None:
    marker_count = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    if marker_count >= 3:
        findings.append(
            ReviewQualityFinding(
                code="mojibake_detected",
                severity="error",
                package_id=package_id,
                feature=feature,
                message=f"{field_name} contains mojibake-like characters; review text encoding is suspect.",
            )
        )


def _validate_evidence_specificity(
    findings: list[ReviewQualityFinding],
    package: FrameEvidencePackage,
    feature: str,
    observed_evidence: str,
) -> None:
    text = observed_evidence.lower()
    frame_tokens = {
        str(package.sampled_frame),
        f"frame {package.sampled_frame}",
        f"frame_{package.sampled_frame:08d}",
        package.package_id.lower(),
    }
    if not any(token.lower() in text for token in frame_tokens):
        findings.append(
            ReviewQualityFinding(
                code="missing_frame_specific_evidence",
                severity="error",
                package_id=package.package_id,
                feature=feature,
                message="observed_evidence must cite the reviewed frame or package id.",
            )
        )

    if package.json_summary and not any(marker.lower() in text for marker in JSON_EVIDENCE_MARKERS):
        findings.append(
            ReviewQualityFinding(
                code="missing_json_specific_evidence",
                severity="error",
                package_id=package.package_id,
                feature=feature,
                message="observed_evidence must cite concrete JSON summary keys, not only the word JSON.",
            )
        )


def _looks_like_template_summary(summary: str) -> bool:
    if not summary:
        return False
    if len(summary) < 180:
        return True
    generic_terms = ("명확한", "이슈", "확인되지", "pass", "acceptable", "RAW/QV/JSON")
    return sum(term in summary for term in generic_terms) >= 3
