"""Report result schemas for Auto VLM."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ACTIVE_REVIEW_FEATURES = frozenset({"OD", "LD", "RBD", "TS", "TL"})


class Judgment(str, Enum):
    LIKELY_ISSUE = "likely_issue"
    POTENTIAL_ISSUE = "potential_issue"
    ACCEPTABLE = "acceptable"
    SYNC_OR_VISUALIZER_ISSUE = "sync_or_visualizer_issue"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    TOOL_ERROR = "tool_error"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FrameTestResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


class ReviewSource(str, Enum):
    UNKNOWN = "unknown"
    MANUAL = "manual"
    ASSISTANT = "assistant"
    PROVIDER = "provider"


class SuspiciousType(str, Enum):
    FN = "FN"
    FP = "FP"
    MISCLASSIFICATION = "misclassification"
    BBOX_OR_GEOMETRY_ERROR = "bbox_or_geometry_error"
    DISTANCE_OR_POSITION_ERROR = "distance_or_position_error"
    VALUE_JUMP = "value_jump"
    ID_SWITCH_OR_DUPLICATION = "id_switch_or_duplication"
    UPDATE_FAILURE = "update_failure"
    FLICKER = "flicker"
    SYNC_OR_OVERLAY_MISMATCH = "sync_or_overlay_mismatch"
    UNCLEAR = "unclear"


@dataclass(frozen=True)
class CandidateAdjudication:
    candidate_id: str
    feature: str
    issue_type: str
    object_ids: tuple[str, ...] = ()
    result: str = "needs_review"
    checked_planes: tuple[str, ...] = ()
    raw_observation: str = ""
    ics_observation: str = ""
    bev_observation: str = ""
    json_observation: str = ""
    decision_reason: str = ""
    summary: str = ""
    observed_evidence: str = ""
    inference: str = ""
    uncertainty: str = ""


@dataclass(frozen=True)
class FeatureReviewResult:
    feature: str
    result: FrameTestResult = FrameTestResult.NEEDS_REVIEW
    confidence: Confidence = Confidence.LOW
    evaluated_issue_types: tuple[str, ...] = ()
    triggered_issue_types: tuple[str, ...] = ()
    summary: str = ""
    observed_evidence: str = ""
    inference: str = ""
    uncertainty: str = ""
    candidate_adjudications: tuple[CandidateAdjudication, ...] = ()


@dataclass(frozen=True)
class ReviewProvenance:
    source: ReviewSource = ReviewSource.UNKNOWN
    reviewer: str = ""
    reviewed_at: str = ""
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    artifact_version: str = ""

    @property
    def label(self) -> str:
        parts = [self.source.value]
        if self.reviewer:
            parts.append(self.reviewer)
        if self.provider:
            parts.append(self.provider)
        if self.model:
            parts.append(self.model)
        return " / ".join(parts)


@dataclass(frozen=True)
class PackageReviewResult:
    judgment: Judgment = Judgment.NEEDS_MORE_EVIDENCE
    confidence: Confidence = Confidence.LOW
    suspicious_type: SuspiciousType = SuspiciousType.UNCLEAR
    review_priority: ReviewPriority = ReviewPriority.MEDIUM
    summary: str = ""
    observed_evidence: str = ""
    inference: str = ""
    uncertainty: str = ""
    need_human_review: bool = True
    tool_status: str = "ok"
    tool_error_message: str = ""
    feature_results: tuple[FeatureReviewResult, ...] = ()
    provenance: ReviewProvenance = ReviewProvenance()

    @property
    def frame_result(self) -> FrameTestResult:
        if self.feature_results:
            feature_values = {feature.result for feature in self.feature_results}
            if FrameTestResult.FAIL in feature_values:
                return FrameTestResult.FAIL
            if FrameTestResult.NEEDS_REVIEW in feature_values:
                return FrameTestResult.NEEDS_REVIEW
            return FrameTestResult.PASS
        if self.judgment in {
            Judgment.LIKELY_ISSUE,
            Judgment.POTENTIAL_ISSUE,
            Judgment.SYNC_OR_VISUALIZER_ISSUE,
            Judgment.TOOL_ERROR,
        }:
            return FrameTestResult.FAIL
        if self.judgment == Judgment.ACCEPTABLE:
            return FrameTestResult.PASS
        return FrameTestResult.NEEDS_REVIEW
