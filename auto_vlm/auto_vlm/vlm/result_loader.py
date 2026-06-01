"""Loader for structured LLM review result artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from auto_vlm.models.results import (
    ACTIVE_REVIEW_FEATURES,
    CandidateAdjudication,
    Confidence,
    FeatureReviewResult,
    FrameTestResult,
    Judgment,
    PackageReviewResult,
    ReviewProvenance,
    ReviewPriority,
    ReviewSource,
    SuspiciousType,
)
from auto_vlm.models.evidence import FrameEvidencePackage
from auto_vlm.models.vlm import Feature
from auto_vlm.vlm.candidates import REQUIRED_CANDIDATE_PLANES, obligations_from_json_summary
from auto_vlm.vlm.reference_context import canonical_issue_type_ids, gtless_single_frame_applicability


class ReviewResultLoadError(ValueError):
    """Raised when llm_review_results.json cannot be converted into report results."""


def load_review_results(path: str | Path) -> dict[str, PackageReviewResult]:
    """Load llm_review_results.json into PackageReviewResult objects keyed by package_id."""
    artifact_path = Path(path)
    try:
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReviewResultLoadError(f"could not read review results: {artifact_path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewResultLoadError(f"review results JSON is malformed: {artifact_path}: {exc}") from exc

    rows = _result_rows(data)
    default_provenance = _load_provenance(data.get("provenance"), "provenance") if isinstance(data, dict) else ReviewProvenance()
    results: dict[str, PackageReviewResult] = {}
    for index, row in enumerate(rows):
        location = f"results[{index}]"
        if not isinstance(row, dict):
            raise ReviewResultLoadError(f"{location} must be an object")
        package_id = _required_text(row, "package_id", location)
        if package_id in results:
            raise ReviewResultLoadError(f"{location}.package_id duplicates {package_id!r}")
        review_mode = _optional_review_mode(row, location)
        feature_results = _load_feature_results(row.get("feature_results"), location, review_mode)
        results[package_id] = PackageReviewResult(
            judgment=_judgment_for(feature_results),
            confidence=_aggregate_confidence(feature_results),
            suspicious_type=SuspiciousType.UNCLEAR,
            review_priority=_review_priority_for(feature_results),
            summary=_join_field(feature_results, "summary"),
            observed_evidence=_join_field(feature_results, "observed_evidence"),
            inference=_join_field(feature_results, "inference"),
            uncertainty=_join_field(feature_results, "uncertainty"),
            need_human_review=any(feature.result != FrameTestResult.PASS for feature in feature_results),
            tool_status="ok",
            feature_results=tuple(feature_results),
            provenance=_load_provenance(row.get("provenance"), f"{location}.provenance", default_provenance),
        )
    return results


def filter_results_for_packages(
    results: dict[str, PackageReviewResult],
    package_ids: set[str],
    packages: list[FrameEvidencePackage] | None = None,
) -> dict[str, PackageReviewResult]:
    missing = sorted(set(results) - package_ids)
    if missing:
        raise ReviewResultLoadError(f"review results reference unknown package_id(s): {', '.join(missing)}")
    filtered = {package_id: result for package_id, result in results.items() if package_id in package_ids}
    if packages is not None:
        _validate_package_candidate_obligations(filtered, packages)
    return filtered


def _result_rows(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    raise ReviewResultLoadError("review results must be a list or an object with a results list")


def _load_feature_results(value: Any, location: str, review_mode: str) -> list[FeatureReviewResult]:
    if not isinstance(value, list) or not value:
        raise ReviewResultLoadError(f"{location}.feature_results must be a non-empty list")
    features: list[FeatureReviewResult] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        item_location = f"{location}.feature_results[{index}]"
        if not isinstance(item, dict):
            raise ReviewResultLoadError(f"{item_location} must be an object")
        feature = _required_text(item, "feature", item_location).upper()
        if feature not in ACTIVE_REVIEW_FEATURES:
            supported = ", ".join(sorted(ACTIVE_REVIEW_FEATURES))
            raise ReviewResultLoadError(f"{item_location}.feature must be one of: {supported}")
        if feature in seen:
            raise ReviewResultLoadError(f"{item_location}.feature duplicates {feature!r}")
        seen.add(feature)
        try:
            result = FrameTestResult(_required_text(item, "result", item_location).lower())
            confidence = Confidence(_required_text(item, "confidence", item_location).lower())
        except ValueError as exc:
            raise ReviewResultLoadError(f"{item_location} has an unsupported enum value: {exc}") from exc
        if result == FrameTestResult.NEEDS_REVIEW:
            raise ReviewResultLoadError(
                f"{item_location}.result must be pass or fail for loaded review results; use confidence/uncertainty for caveats"
            )
        evaluated_issue_types = _required_text_list(item, "evaluated_issue_types", item_location)
        triggered_issue_types = _optional_text_list(item, "triggered_issue_types", item_location)
        observed_evidence = _required_text(item, "observed_evidence", item_location)
        _validate_observed_evidence_sources(observed_evidence, item_location)
        candidate_adjudications = _load_candidate_adjudications(
            item.get("candidate_adjudications"),
            item_location,
            feature,
        )
        _validate_issue_types(
            feature,
            evaluated_issue_types,
            triggered_issue_types,
            item_location,
            review_mode,
        )
        features.append(
            FeatureReviewResult(
                feature=feature,
                result=result,
                confidence=confidence,
                evaluated_issue_types=evaluated_issue_types,
                triggered_issue_types=triggered_issue_types,
                summary=_required_text(item, "summary", item_location),
                observed_evidence=observed_evidence,
                inference=_required_text(item, "inference", item_location),
                uncertainty=_required_text(item, "uncertainty", item_location),
                candidate_adjudications=tuple(candidate_adjudications),
            )
        )
    return features


def _load_candidate_adjudications(
    value: Any,
    location: str,
    feature: str,
) -> list[CandidateAdjudication]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ReviewResultLoadError(f"{location}.candidate_adjudications must be a list when provided")

    adjudications: list[CandidateAdjudication] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        item_location = f"{location}.candidate_adjudications[{index}]"
        if not isinstance(item, dict):
            raise ReviewResultLoadError(f"{item_location} must be an object")
        candidate_id = _required_text(item, "candidate_id", item_location)
        if candidate_id in seen:
            raise ReviewResultLoadError(f"{item_location}.candidate_id duplicates {candidate_id!r}")
        seen.add(candidate_id)
        candidate_feature = _required_text(item, "feature", item_location).upper()
        if candidate_feature != feature:
            raise ReviewResultLoadError(
                f"{item_location}.feature must match parent feature {feature}"
            )
        result = _candidate_decision(item, item_location)
        if result not in {"issue", "cleared", "uncertain"}:
            raise ReviewResultLoadError(
                f"{item_location}.result must be one of: issue, cleared, uncertain"
            )
        checked_planes = _required_text_list(item, "checked_planes", item_location)
        unknown_planes = sorted(set(checked_planes) - REQUIRED_CANDIDATE_PLANES)
        if unknown_planes:
            raise ReviewResultLoadError(
                f"{item_location}.checked_planes contains unknown plane(s): {', '.join(unknown_planes)}"
            )
        raw_observation = _required_text(item, "raw_observation", item_location)
        ics_observation = _required_text(item, "ics_observation", item_location)
        bev_observation = _required_text(item, "bev_observation", item_location)
        json_observation = _required_text(item, "json_observation", item_location)
        decision_reason = _required_text(item, "decision_reason", item_location)
        observed_evidence = _optional_reasoning_text(
            item,
            "observed_evidence",
            item_location,
            f"raw: {raw_observation}; ics: {ics_observation}; bev: {bev_observation}; json: {json_observation}",
        )
        _validate_candidate_observation_sources(
            raw_observation,
            ics_observation,
            bev_observation,
            json_observation,
            item_location,
        )
        issue_type = _required_text(item, "issue_type", item_location)
        inference = _optional_reasoning_text(item, "inference", item_location, decision_reason)
        _validate_candidate_issue_evidence(
            item_location,
            issue_type,
            result,
            f"{observed_evidence} {bev_observation} {json_observation}",
            f"{inference} {decision_reason}",
        )
        adjudications.append(
            CandidateAdjudication(
                candidate_id=candidate_id,
                feature=candidate_feature,
                issue_type=issue_type,
                object_ids=_optional_text_list(item, "object_ids", item_location),
                result=result,
                checked_planes=checked_planes,
                raw_observation=raw_observation,
                ics_observation=ics_observation,
                bev_observation=bev_observation,
                json_observation=json_observation,
                decision_reason=decision_reason,
                summary=_optional_reasoning_text(
                    item,
                    "summary",
                    item_location,
                    f"{candidate_id}: {result}",
                ),
                observed_evidence=observed_evidence,
                inference=inference,
                uncertainty=_required_text(item, "uncertainty", item_location),
            )
        )
    return adjudications


def _candidate_decision(data: dict[str, Any], location: str) -> str:
    result = data.get("decision", data.get("result"))
    if not isinstance(result, str) or not result.strip():
        raise ReviewResultLoadError(f"{location}.decision is required")
    return result.strip().lower()


def _optional_reasoning_text(
    data: dict[str, Any],
    field_name: str,
    location: str,
    default: str,
) -> str:
    value = data.get(field_name)
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise ReviewResultLoadError(f"{location}.{field_name} must be a non-empty string when provided")
    return value.strip()


def _validate_candidate_observation_sources(
    raw_observation: str,
    ics_observation: str,
    bev_observation: str,
    json_observation: str,
    location: str,
) -> None:
    missing = []
    if not any(token in raw_observation.lower() for token in ("raw", "source frame", "원본")):
        missing.append("raw_observation")
    if not any(token in ics_observation.lower() for token in ("ics", "qv", "overlay", "오버레이")):
        missing.append("ics_observation")
    if not any(token in bev_observation.lower() for token in ("bev", "vcs", "world-space", "world space", "grid")):
        missing.append("bev_observation")
    if "json" not in json_observation.lower():
        missing.append("json_observation")
    if missing:
        raise ReviewResultLoadError(
            f"{location} must include concrete raw/ICS/BEV/JSON observation fields; missing or vague: {', '.join(missing)}"
        )


def _validate_candidate_issue_evidence(
    location: str,
    issue_type: str,
    result: str,
    observed_evidence: str,
    inference: str,
) -> None:
    if result != "issue" or issue_type != "DEF-OD-BBOX-DUP":
        return

    text = f"{observed_evidence} {inference}".lower()
    quantitative_bev_markers = (
        "long_distance",
        "lat_distance",
        "delta_long",
        "delta_lat",
        "bev_center_distance",
    )
    if not any(marker in text for marker in quantitative_bev_markers):
        raise ReviewResultLoadError(
            f"{location} DEF-OD-BBOX-DUP issue must cite quantitative BEV/VCS world-space evidence"
        )


def _load_provenance(
    value: Any,
    location: str,
    default: ReviewProvenance | None = None,
) -> ReviewProvenance:
    if value is None:
        return default or ReviewProvenance()
    if not isinstance(value, dict):
        raise ReviewResultLoadError(f"{location} must be an object when provided")

    def optional_text(field_name: str) -> str:
        raw = value.get(field_name, "")
        if raw is None:
            return ""
        if not isinstance(raw, str):
            raise ReviewResultLoadError(f"{location}.{field_name} must be a string")
        return raw.strip()

    source_raw = optional_text("source").lower() or (default.source.value if default else ReviewSource.UNKNOWN.value)
    try:
        source = ReviewSource(source_raw)
    except ValueError as exc:
        supported = ", ".join(item.value for item in ReviewSource)
        raise ReviewResultLoadError(f"{location}.source must be one of: {supported}") from exc

    default = default or ReviewProvenance()
    return ReviewProvenance(
        source=source,
        reviewer=optional_text("reviewer") or default.reviewer,
        reviewed_at=optional_text("reviewed_at") or default.reviewed_at,
        provider=optional_text("provider") or default.provider,
        model=optional_text("model") or default.model,
        prompt_version=optional_text("prompt_version") or default.prompt_version,
        artifact_version=optional_text("artifact_version") or default.artifact_version,
    )


def _required_text(data: dict[str, Any], field_name: str, location: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ReviewResultLoadError(f"{location}.{field_name} is required")
    return value.strip()


def _required_text_list(data: dict[str, Any], field_name: str, location: str) -> tuple[str, ...]:
    values = _optional_text_list(data, field_name, location)
    if not values:
        raise ReviewResultLoadError(f"{location}.{field_name} must be a non-empty list")
    return values


def _optional_text_list(data: dict[str, Any], field_name: str, location: str) -> tuple[str, ...]:
    value = data.get(field_name, [])
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ReviewResultLoadError(f"{location}.{field_name} must be a list")
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ReviewResultLoadError(f"{location}.{field_name}[{index}] must be a non-empty string")
        normalized = item.strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _validate_issue_types(
    feature: str,
    evaluated_issue_types: tuple[str, ...],
    triggered_issue_types: tuple[str, ...],
    location: str,
    review_mode: str,
) -> None:
    feature_enum = Feature(feature)
    canonical = set(canonical_issue_type_ids(feature_enum))
    applicability = gtless_single_frame_applicability(feature_enum)
    evaluated = set(evaluated_issue_types)
    triggered = set(triggered_issue_types)
    if review_mode == "gt_reference":
        expected_evaluated = canonical
    else:
        expected_evaluated = {
            issue_id for issue_id, status in applicability.items() if status != "not_evaluable"
        }

    unknown_evaluated = sorted(evaluated - canonical)
    if unknown_evaluated:
        raise ReviewResultLoadError(
            f"{location}.evaluated_issue_types contains unknown issue type(s): {', '.join(unknown_evaluated)}"
        )

    missing_evaluated = sorted(expected_evaluated - evaluated)
    if missing_evaluated:
        raise ReviewResultLoadError(
            f"{location}.evaluated_issue_types is missing GT-less evaluable issue type(s): {', '.join(missing_evaluated)}"
        )

    incorrectly_evaluated = sorted(evaluated - expected_evaluated)
    if incorrectly_evaluated:
        raise ReviewResultLoadError(
            f"{location}.evaluated_issue_types contains GT-less non-evaluable issue type(s): {', '.join(incorrectly_evaluated)}"
        )

    unknown_triggered = sorted(triggered - canonical)
    if unknown_triggered:
        raise ReviewResultLoadError(
            f"{location}.triggered_issue_types contains unknown issue type(s): {', '.join(unknown_triggered)}"
        )
    unchecked_triggered = sorted(triggered - evaluated)
    if unchecked_triggered:
        raise ReviewResultLoadError(
            f"{location}.triggered_issue_types must be included in evaluated_issue_types: {', '.join(unchecked_triggered)}"
        )


def _validate_observed_evidence_sources(observed_evidence: str, location: str) -> None:
    """Require every feature review to cite the three evidence planes it used."""
    text = observed_evidence.lower()
    missing = []
    if not any(token in text for token in ("raw", "source frame", "원본")):
        missing.append("raw frame")
    if not any(token in text for token in ("qv", "overlay", "오버레이")):
        missing.append("QV overlay")
    if not any(token in text for token in ("bev", "vcs", "world-space", "world space", "grid")):
        missing.append("BEV/VCS")
    if "json" not in text:
        missing.append("JSON")
    if missing:
        raise ReviewResultLoadError(
            f"{location}.observed_evidence must cite raw frame, QV overlay, BEV/VCS, and JSON evidence; missing: {', '.join(missing)}"
        )


def _optional_review_mode(data: dict[str, Any], location: str) -> str:
    value = data.get("review_mode", "gtless_single_frame")
    if not isinstance(value, str) or not value.strip():
        raise ReviewResultLoadError(f"{location}.review_mode must be a string when provided")
    review_mode = value.strip()
    if review_mode not in {"gtless_single_frame", "gt_reference"}:
        raise ReviewResultLoadError(
            f"{location}.review_mode must be one of: gtless_single_frame, gt_reference"
        )
    return review_mode


def _aggregate_confidence(features: list[FeatureReviewResult]) -> Confidence:
    values = {feature.confidence for feature in features}
    if Confidence.LOW in values:
        return Confidence.LOW
    if Confidence.MEDIUM in values:
        return Confidence.MEDIUM
    return Confidence.HIGH


def _review_priority_for(features: list[FeatureReviewResult]) -> ReviewPriority:
    if any(feature.result == FrameTestResult.FAIL for feature in features):
        return ReviewPriority.HIGH
    if any(feature.result == FrameTestResult.NEEDS_REVIEW for feature in features):
        return ReviewPriority.MEDIUM
    return ReviewPriority.LOW


def _judgment_for(features: list[FeatureReviewResult]) -> Judgment:
    if any(feature.result == FrameTestResult.FAIL for feature in features):
        return Judgment.LIKELY_ISSUE
    if any(feature.result == FrameTestResult.NEEDS_REVIEW for feature in features):
        return Judgment.NEEDS_MORE_EVIDENCE
    return Judgment.ACCEPTABLE


def _join_field(features: list[FeatureReviewResult], field_name: str) -> str:
    return " | ".join(f"{feature.feature}: {getattr(feature, field_name)}" for feature in features)


def _validate_package_candidate_obligations(
    results: dict[str, PackageReviewResult],
    packages: list[FrameEvidencePackage],
) -> None:
    for package in packages:
        if package.package_id not in results:
            continue
        result = results[package.package_id]
        features_by_name = {feature.feature: feature for feature in result.feature_results}
        _validate_feature_four_plane_evidence(package, result)
        obligations = obligations_from_json_summary(package.json_summary)
        if not obligations:
            continue
        candidate_packets = {
            packet.candidate_id: packet
            for packet in getattr(package, "candidate_evidence_packets", ())
        }
        for obligation in obligations:
            feature = features_by_name.get(obligation.feature)
            if feature is None:
                raise ReviewResultLoadError(
                    f"{package.package_id} is missing feature result for candidate {obligation.candidate_id}"
                )
            adjudications = {
                adjudication.candidate_id: adjudication
                for adjudication in feature.candidate_adjudications
            }
            adjudication = adjudications.get(obligation.candidate_id)
            if adjudication is None:
                raise ReviewResultLoadError(
                    f"{package.package_id} must adjudicate candidate {obligation.candidate_id}"
                )
            packet = candidate_packets.get(obligation.candidate_id)
            if packet is None and getattr(package, "candidate_evidence_packets", ()):
                raise ReviewResultLoadError(
                    f"{package.package_id} candidate {obligation.candidate_id} is missing candidate evidence packet"
                )
            if packet is not None:
                _validate_candidate_four_plane_artifacts(package.package_id, obligation.candidate_id, packet, adjudication)
            missing_planes = sorted(REQUIRED_CANDIDATE_PLANES - set(adjudication.checked_planes))
            if missing_planes:
                raise ReviewResultLoadError(
                    f"{package.package_id} candidate {obligation.candidate_id} missing checked plane(s): {', '.join(missing_planes)}"
                )
            if adjudication.issue_type != obligation.issue_type:
                raise ReviewResultLoadError(
                    f"{package.package_id} candidate {obligation.candidate_id} issue_type must be {obligation.issue_type}"
                )
            if adjudication.object_ids and adjudication.object_ids != obligation.object_ids:
                raise ReviewResultLoadError(
                    f"{package.package_id} candidate {obligation.candidate_id} object_ids must be {', '.join(obligation.object_ids)}"
                )
            if adjudication.result == "issue" and obligation.issue_type not in feature.triggered_issue_types:
                raise ReviewResultLoadError(
                    f"{package.package_id} candidate {obligation.candidate_id} is issue but {obligation.issue_type} is not triggered"
                )
            if adjudication.result in {"needs_review", "uncertain"}:
                raise ReviewResultLoadError(
                    f"{package.package_id} candidate {obligation.candidate_id} must be adjudicated as issue or cleared before report generation"
                )
            if feature.result == FrameTestResult.PASS and adjudication.result != "cleared":
                raise ReviewResultLoadError(
                    f"{package.package_id} feature {feature.feature} cannot pass with unresolved candidate {obligation.candidate_id}"
                )


def _validate_feature_four_plane_evidence(
    package: FrameEvidencePackage,
    result: PackageReviewResult,
) -> None:
    packets = {
        packet.feature: packet
        for packet in getattr(package, "feature_evidence_packets", ())
    }
    if not packets:
        return
    for feature in result.feature_results:
        packet = packets.get(feature.feature)
        if packet is None:
            continue
        missing = []
        if packet.raw_frame_image is None:
            missing.append("raw_frame_image")
        if packet.ics_crop_image is None:
            missing.append("ics_crop_image")
        if packet.bev_crop_image is None:
            missing.append("bev_crop_image")
        if packet.json_snippet is None:
            missing.append("json_snippet")
        if missing:
            raise ReviewResultLoadError(
                f"{package.package_id} feature {feature.feature} is missing evidence artifact(s): {', '.join(missing)}"
            )
        _require_text_cites_path(
            feature.observed_evidence,
            packet.raw_frame_image,
            f"{package.package_id}.{feature.feature}.observed_evidence",
            "raw_frame_image",
        )
        _require_text_cites_path(
            feature.observed_evidence,
            packet.ics_crop_image,
            f"{package.package_id}.{feature.feature}.observed_evidence",
            "ics_crop_image",
        )
        _require_text_cites_path(
            feature.observed_evidence,
            packet.bev_crop_image,
            f"{package.package_id}.{feature.feature}.observed_evidence",
            "bev_crop_image",
        )


def _validate_candidate_four_plane_artifacts(
    package_id: str,
    candidate_id: str,
    packet: Any,
    adjudication: CandidateAdjudication,
) -> None:
    missing = []
    if packet.raw_frame_image is None:
        missing.append("raw_frame_image")
    if packet.ics_crop_image is None:
        missing.append("ics_crop_image")
    if packet.bev_crop_image is None:
        missing.append("bev_crop_image")
    if packet.candidate_json_values is None:
        missing.append("candidate_json_values")
    if missing:
        raise ReviewResultLoadError(
            f"{package_id} candidate {candidate_id} is missing evidence artifact(s): {', '.join(missing)}"
        )
    if str(packet.bev_crop_status).lower().startswith("unavailable"):
        raise ReviewResultLoadError(
            f"{package_id} candidate {candidate_id} has unavailable BEV evidence: {packet.bev_crop_status}"
        )

    fields = {
        "raw_observation": (adjudication.raw_observation, packet.raw_frame_image),
        "ics_observation": (adjudication.ics_observation, packet.ics_crop_image),
        "bev_observation": (adjudication.bev_observation, packet.bev_crop_image),
        "json_observation": (adjudication.json_observation, packet.candidate_json_values),
    }
    for field_name, (text, path) in fields.items():
        _require_text_cites_path(
            text,
            path,
            f"{package_id}.{candidate_id}.{field_name}",
            field_name,
        )


def _require_text_cites_path(text: str, path: Any, location: str, plane_name: str) -> None:
    path_text = str(path)
    if not path_text:
        raise ReviewResultLoadError(f"{location} cannot cite missing {plane_name}")
    normalized_text = text.replace("/", "\\").lower()
    normalized_path = path_text.replace("/", "\\").lower()
    filename = Path(path_text).name.lower()
    if normalized_path not in normalized_text and filename not in normalized_text:
        raise ReviewResultLoadError(
            f"{location} must cite the actual {plane_name} artifact path or filename: {path_text}"
        )
