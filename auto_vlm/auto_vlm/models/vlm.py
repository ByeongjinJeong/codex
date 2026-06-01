"""Optional VLM evaluation contract schemas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from auto_vlm.models.results import Confidence, Judgment, ReviewPriority, SuspiciousType


class Feature(str, Enum):
    OD = "OD"
    LD = "LD"
    RBD = "RBD"
    TS = "TS"
    TL = "TL"
    ALL = "ALL"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FeatureReviewContext:
    feature: Feature
    qv_json_interpretation: list[str]
    issue_type_guidance: list[str]
    inspection_checklist: list[str]
    reference_sources: list[str]
    must_not: list[str]

    def __post_init__(self) -> None:
        if self.feature in (Feature.ALL, Feature.UNKNOWN):
            raise ValueError("FeatureReviewContext requires a concrete feature")
        for field_name in (
            "qv_json_interpretation",
            "issue_type_guidance",
            "inspection_checklist",
            "reference_sources",
            "must_not",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "feature": self.feature.value,
            "qv_json_interpretation": list(self.qv_json_interpretation),
            "issue_type_guidance": list(self.issue_type_guidance),
            "inspection_checklist": list(self.inspection_checklist),
            "reference_sources": list(self.reference_sources),
            "must_not": list(self.must_not),
        }


@dataclass(frozen=True)
class VlmEvaluationResult:
    judgment: Judgment
    confidence: Confidence
    feature: Feature
    suspicious_type: SuspiciousType
    review_priority: ReviewPriority
    summary: str
    observed_evidence: str
    inference: str
    uncertainty: str

    def __post_init__(self) -> None:
        for field_name in ("summary", "observed_evidence", "inference", "uncertainty"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} is required")

    @classmethod
    def from_mapping(cls, data: dict[str, str]) -> "VlmEvaluationResult":
        return cls(
            judgment=Judgment(data["judgment"]),
            confidence=Confidence(data["confidence"]),
            feature=Feature(data["feature"]),
            suspicious_type=SuspiciousType(data["suspicious_type"]),
            review_priority=ReviewPriority(data["review_priority"]),
            summary=data["summary"],
            observed_evidence=data["observed_evidence"],
            inference=data["inference"],
            uncertainty=data["uncertainty"],
        )
