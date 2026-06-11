"""Korean report text normalization helpers."""

from __future__ import annotations

from auto_vlm.models.evidence import FrameEvidencePackage
from auto_vlm.models.results import FeatureReviewResult, FrameTestResult


def feature_summary(package: FrameEvidencePackage, feature: FeatureReviewResult) -> str:
    if feature.result == FrameTestResult.PASS:
        return (
            f"{package.case_id} frame {package.sampled_frame} {feature.feature}는 "
            f"raw/ICS(QV)/BEV/JSON 4-plane 검토 결과 "
            f"{_issue_list(feature.evaluated_issue_types)}에서 단일 프레임 기준 결함이 확인되지 않아 pass입니다."
        )

    if feature.result == FrameTestResult.FAIL:
        if _looks_korean(feature.summary):
            return feature.summary
        triggered = _issue_list(feature.triggered_issue_types) or "검출 이슈"
        return (
            f"{package.case_id} frame {package.sampled_frame} {feature.feature}는 "
            f"raw/ICS(QV)/BEV/JSON 4-plane 검토 결과 {triggered} 이슈가 확인되어 fail입니다."
        )

    if _looks_korean(feature.summary):
        return feature.summary
    return (
        f"{package.case_id} frame {package.sampled_frame} {feature.feature}는 "
        "추가 검토가 필요합니다."
    )


def feature_observed_evidence(package: FrameEvidencePackage, feature: FeatureReviewResult) -> str:
    evidence = _package_evidence(package)
    return (
        f"{package.case_id} frame {package.sampled_frame} {feature.feature} 관찰 증거: "
        f"{evidence}"
    )


def feature_inference(package: FrameEvidencePackage, feature: FeatureReviewResult) -> str:
    evaluated = _issue_list(feature.evaluated_issue_types)
    triggered = _issue_list(feature.triggered_issue_types)
    if feature.result == FrameTestResult.PASS:
        return (
            f"{package.case_id} frame {package.sampled_frame} {feature.feature} 판단: "
            f"{evaluated}를 검토했으나 triggered issue가 없어 pass로 판정합니다."
    )
    if feature.result == FrameTestResult.FAIL:
        return (
            f"{package.case_id} frame {package.sampled_frame} {feature.feature} 판단: "
            f"{triggered or '검출 이슈'}가 raw/ICS(QV)/BEV/JSON 증거와 JSON 값으로 뒷받침되어 fail로 판정합니다."
        )
    return (
        f"{package.case_id} frame {package.sampled_frame} {feature.feature} 판단: "
        "현재 증거만으로 pass/fail 확정이 어려워 추가 검토가 필요합니다."
    )


def feature_uncertainty(package: FrameEvidencePackage, feature: FeatureReviewResult) -> str:
    return (
        f"{package.case_id} frame {package.sampled_frame} {feature.feature} 불확실성: "
        "GT-less 단일 프레임 검토 결과입니다. 시간축 연속성, GT 전용 누락, "
        "인접 프레임 변화는 이번 판정 범위에 포함하지 않았습니다."
    )


def _package_evidence(package: FrameEvidencePackage) -> str:
    raw = str(package.raw_frame_image) if package.raw_frame_image else ""
    qv = str(package.qv_overlay_frame_image or package.center_frame_image)
    json_path = str(package.json_snippet) if package.json_snippet else ""
    summary = package.json_summary or ""
    return (
        f"raw_frame_image={raw}; "
        f"qv_overlay_frame_image={qv}; "
        f"json_snippet={json_path}; "
        f"JSON summary={summary}."
    )


def _issue_list(values: tuple[str, ...]) -> str:
    return ", ".join(values)


def _looks_korean(text: str) -> bool:
    return any("가" <= char <= "힣" for char in text or "")
