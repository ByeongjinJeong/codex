"""Feature-specific context builder for VLM review packets."""

from __future__ import annotations

from auto_vlm.models.vlm import Feature, FeatureReviewContext
from auto_vlm.vlm.reference_context import (
    load_adas_must_not,
    load_adas_feature_checklist,
    load_issue_type_scan_checklist,
    load_issue_type_guidance,
    load_qv_json_interpretation,
    reference_sources_for,
)


ACTIVE_FEATURES = (Feature.OD, Feature.LD, Feature.RBD, Feature.TS, Feature.TL)


def build_feature_review_contexts(focus_feature: str) -> list[FeatureReviewContext]:
    feature = Feature(focus_feature)
    selected = ACTIVE_FEATURES if feature == Feature.ALL else (feature,)
    unsupported = [item for item in selected if item not in ACTIVE_FEATURES]
    if unsupported:
        raise ValueError(f"unsupported VLM review feature: {unsupported[0].value}")

    return [_build_context(item) for item in selected]


def _build_context(feature: Feature) -> FeatureReviewContext:
    inspection_checklist = load_adas_feature_checklist(feature) + load_issue_type_scan_checklist(feature)
    return FeatureReviewContext(
        feature=feature,
        qv_json_interpretation=load_qv_json_interpretation(feature),
        issue_type_guidance=load_issue_type_guidance(feature),
        inspection_checklist=inspection_checklist,
        reference_sources=reference_sources_for(feature),
        must_not=load_adas_must_not(),
    )
