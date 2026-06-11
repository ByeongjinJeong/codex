from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from auto_vlm.models.results import Confidence, FrameTestResult, Judgment, ReviewPriority, ReviewSource
from auto_vlm.models.vlm import Feature
from auto_vlm.vlm.reference_context import canonical_issue_type_ids, gtless_single_frame_applicability
from auto_vlm.vlm.result_loader import ReviewResultLoadError, filter_results_for_packages, load_review_results


def _issue_ids(feature: str) -> list[str]:
    return list(canonical_issue_type_ids(Feature(feature)))


def _evaluated_ids(feature: str) -> list[str]:
    applicability = gtless_single_frame_applicability(Feature(feature))
    return [issue_id for issue_id in _issue_ids(feature) if applicability[issue_id] != "not_evaluable"]


def _review_row(package_id: str = "CASE_001__frame_00000100") -> dict:
    return {
        "package_id": package_id,
        "case_id": "CASE_001",
        "sampled_frame": 100,
        "feature_results": [
            {
                "feature": "OD",
                "result": "fail",
                "confidence": "low",
                "evaluated_issue_types": _evaluated_ids("OD"),
                "triggered_issue_types": ["DEF-OD-FN"],
                "summary": "object detection is unstable",
                "observed_evidence": "raw frame shows the object; QV overlay misses it; BEV/VCS grid confirms the miss; JSON object count is lower than expected",
                "inference": "OD fails this frame",
                "uncertainty": "single-frame judgment",
            },
            {
                "feature": "LD",
                "result": "pass",
                "confidence": "medium",
                "evaluated_issue_types": _evaluated_ids("LD"),
                "triggered_issue_types": [],
                "summary": "lanes align with road markings",
                "observed_evidence": "raw frame lane markings match QV overlay lane lines, BEV/VCS geometry, and JSON lane entries",
                "inference": "LD passes this frame",
                "uncertainty": "none from available evidence",
            },
        ],
    }


def test_load_review_results_converts_feature_rows(tmp_path):
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [_review_row()]}), encoding="utf-8")

    results = load_review_results(path)
    result = results["CASE_001__frame_00000100"]

    assert result.frame_result == FrameTestResult.FAIL
    assert result.judgment == Judgment.LIKELY_ISSUE
    assert result.confidence == Confidence.LOW
    assert result.review_priority == ReviewPriority.HIGH
    assert result.need_human_review is True
    assert [feature.feature for feature in result.feature_results] == ["OD", "LD"]
    assert result.feature_results[0].evaluated_issue_types == tuple(_evaluated_ids("OD"))
    assert result.feature_results[0].triggered_issue_types == ("DEF-OD-FN",)
    assert result.provenance.source == ReviewSource.UNKNOWN


def test_load_review_results_applies_top_level_provenance(tmp_path):
    path = tmp_path / "llm_review_results.json"
    path.write_text(
        json.dumps(
            {
                "provenance": {
                    "source": "assistant",
                    "reviewer": "Codex",
                    "reviewed_at": "2026-05-22T13:30:00+09:00",
                    "model": "gpt-5",
                    "prompt_version": "vlm_packet_v1",
                    "artifact_version": "review_results_v1",
                },
                "results": [_review_row()],
            }
        ),
        encoding="utf-8",
    )

    result = load_review_results(path)["CASE_001__frame_00000100"]

    assert result.provenance.source == ReviewSource.ASSISTANT
    assert result.provenance.reviewer == "Codex"
    assert result.provenance.model == "gpt-5"
    assert result.provenance.prompt_version == "vlm_packet_v1"
    assert result.provenance.artifact_version == "review_results_v1"


def test_load_review_results_row_provenance_overrides_top_level(tmp_path):
    row = _review_row()
    row["provenance"] = {"source": "manual", "reviewer": "review engineer"}
    path = tmp_path / "llm_review_results.json"
    path.write_text(
        json.dumps(
            {
                "provenance": {"source": "assistant", "reviewer": "Codex", "model": "gpt-5"},
                "results": [row],
            }
        ),
        encoding="utf-8",
    )

    result = load_review_results(path)["CASE_001__frame_00000100"]

    assert result.provenance.source == ReviewSource.MANUAL
    assert result.provenance.reviewer == "review engineer"
    assert result.provenance.model == "gpt-5"


def test_load_review_results_rejects_bad_provenance_source(tmp_path):
    path = tmp_path / "llm_review_results.json"
    path.write_text(
        json.dumps({"provenance": {"source": "spreadsheet"}, "results": [_review_row()]}),
        encoding="utf-8",
    )

    with pytest.raises(ReviewResultLoadError, match="provenance.source must be one of"):
        load_review_results(path)


def test_load_review_results_rejects_unsupported_feature(tmp_path):
    row = _review_row()
    row["feature_results"][0]["feature"] = "FCW"
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps([row]), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="feature must be one of"):
        load_review_results(path)


def test_load_review_results_requires_reasoning_fields(tmp_path):
    row = _review_row()
    row["feature_results"][0]["inference"] = ""
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="inference is required"):
        load_review_results(path)


def test_load_review_results_requires_feature_evidence_sources(tmp_path):
    row = _review_row()
    row["feature_results"][0]["observed_evidence"] = "QV overlay misses a visible object"
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="must cite raw frame, QV overlay, and JSON evidence"):
        load_review_results(path)


def test_load_review_results_requires_evaluated_issue_types(tmp_path):
    row = _review_row()
    row["feature_results"][0]["evaluated_issue_types"] = []
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="evaluated_issue_types must be a non-empty list"):
        load_review_results(path)


def test_load_review_results_requires_all_canonical_issue_types(tmp_path):
    row = _review_row()
    row["feature_results"][0]["evaluated_issue_types"] = _evaluated_ids("OD")[:-1]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="missing GT-less evaluable issue type"):
        load_review_results(path)


def test_load_review_results_rejects_unknown_issue_type(tmp_path):
    row = _review_row()
    row["feature_results"][0]["evaluated_issue_types"] = _evaluated_ids("OD") + ["DEF-OD-UNKNOWN"]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="unknown issue type"):
        load_review_results(path)


def test_load_review_results_rejects_gtless_non_evaluable_as_evaluated(tmp_path):
    row = _review_row()
    row["feature_results"][0]["evaluated_issue_types"] = _evaluated_ids("OD") + ["DEF-OD-VELOCITY"]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="GT-less non-evaluable"):
        load_review_results(path)


def test_load_review_results_rejects_triggered_issue_outside_canonical_set(tmp_path):
    row = _review_row()
    row["feature_results"][0]["triggered_issue_types"] = ["DEF-OD-UNKNOWN"]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="triggered_issue_types contains unknown"):
        load_review_results(path)


def test_filter_results_for_packages_rejects_unknown_package_id(tmp_path):
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps([_review_row("UNKNOWN__frame_00000001")]), encoding="utf-8")
    results = load_review_results(path)

    with pytest.raises(ReviewResultLoadError, match="unknown package_id"):
        filter_results_for_packages(results, {"CASE_001__frame_00000100"})


def test_filter_results_for_packages_does_not_require_legacy_adjudication(tmp_path):
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [_review_row()]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=11; OD_bbox_overlap_" + "candi" + "dates=171-183:min_overlap=0.79,iou=0.15",
        feature_evidence_packets=(),
    )

    filtered = filter_results_for_packages(results, {package.package_id}, packages=[package])

    assert package.package_id in filtered


def test_load_review_results_rejects_feature_needs_review(tmp_path):
    row = _review_row()
    row["feature_results"][0]["result"] = "needs_review"
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="result must be pass or fail"):
        load_review_results(path)
