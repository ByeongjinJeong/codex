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


def _candidate_adjudication(
    candidate_id: str = "OD_BBOX_DUP_171_183",
    result: str = "cleared",
) -> dict:
    observed_evidence = "raw frame has two visible objects; QV overlay has ICS overlap; BEV/VCS separates them; JSON reports the overlap candidate"
    inference = "candidate is cleared by BEV/VCS separation"
    if result == "issue":
        observed_evidence = (
            "raw frame and QV overlay show duplicate boxes; JSON/BEV reports "
            "Long_Distance=31.50m, Lat_Distance=6.53m and Long_Distance=31.70m, "
            "Lat_Distance=6.61m for the two IDs"
        )
        inference = "candidate is an issue because delta_long=0.20m, delta_lat=0.08m, bev_center_distance=0.22m"
    return {
        "candidate_id": candidate_id,
        "feature": "OD",
        "issue_type": "DEF-OD-BBOX-DUP",
        "object_ids": ["171", "183"],
        "result": result,
        "checked_planes": ["raw", "ics", "bev_vcs", "json"],
        "raw_observation": f"raw frame shows candidate {candidate_id} with object ids 171 and 183",
        "ics_observation": f"ICS/QV overlay shows candidate {candidate_id} with object ids 171 and 183",
        "bev_observation": f"BEV/VCS world-space view separates candidate {candidate_id} object ids 171 and 183",
        "json_observation": f"JSON reports candidate {candidate_id} object ids 171 and 183",
        "decision_reason": inference,
        "summary": "candidate was checked across all planes",
        "observed_evidence": observed_evidence,
        "inference": inference,
        "uncertainty": "single-frame review",
    }


def _candidate_packet(candidate_id: str = "OD_BBOX_DUP_171_183") -> SimpleNamespace:
    return SimpleNamespace(
        candidate_id=candidate_id,
        raw_frame_image=Path("raw_frame.jpg"),
        ics_crop_image=Path(f"{candidate_id}__ics.jpg"),
        bev_crop_image=Path(f"{candidate_id}__bev.jpg"),
        bev_crop_status="available_overlay_right_of_raw",
        candidate_json_values=Path(f"{candidate_id}__json.json"),
    )


def _with_artifact_citations(candidate: dict) -> dict:
    candidate_id = candidate["candidate_id"]
    candidate["raw_observation"] += " raw_frame.jpg"
    candidate["ics_observation"] += f" {candidate_id}__ics.jpg"
    candidate["bev_observation"] += f" {candidate_id}__bev.jpg"
    candidate["json_observation"] += f" {candidate_id}__json.json"
    return candidate


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


def test_filter_results_for_packages_requires_candidate_adjudication_when_json_summary_has_candidate(tmp_path):
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [_review_row()]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=11; OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15",
    )

    with pytest.raises(ReviewResultLoadError, match="must adjudicate candidate OD_BBOX_DUP_171_183"):
        filter_results_for_packages(results, {package.package_id}, packages=[package])


def test_filter_results_for_packages_requires_large_bbox_candidate_adjudication(tmp_path):
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [_review_row()]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=8; OD_large_bbox_candidates=60:w=0.30,h=0.51,area=0.15",
    )

    with pytest.raises(ReviewResultLoadError, match="must adjudicate candidate OD_BBOX_FIT_LARGE_60"):
        filter_results_for_packages(results, {package.package_id}, packages=[package])


def test_filter_results_for_packages_requires_low_road_edge_candidate_adjudication(tmp_path):
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [_review_row()]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=8; road_edges=1; RBD_low_road_edge_count=1/expected_min=2",
    )

    with pytest.raises(ReviewResultLoadError, match="candidate RBD_LOW_ROAD_EDGE_COUNT_1_OF_2"):
        filter_results_for_packages(results, {package.package_id}, packages=[package])


def test_filter_results_for_packages_accepts_cleared_candidate_with_all_planes(tmp_path):
    row = _review_row()
    row["feature_results"][0]["triggered_issue_types"] = []
    row["feature_results"][0]["result"] = "pass"
    row["feature_results"][0]["candidate_adjudications"] = [_candidate_adjudication()]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=11; OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15",
    )

    filtered = filter_results_for_packages(results, {package.package_id}, packages=[package])

    adjudication = filtered[package.package_id].feature_results[0].candidate_adjudications[0]
    assert adjudication.candidate_id == "OD_BBOX_DUP_171_183"
    assert adjudication.result == "cleared"


def test_filter_results_for_packages_requires_candidate_observations_to_cite_raw_ics_bev_json_artifacts(tmp_path):
    row = _review_row()
    row["feature_results"][0]["triggered_issue_types"] = []
    row["feature_results"][0]["result"] = "pass"
    candidate = _with_artifact_citations(_candidate_adjudication())
    candidate["bev_observation"] = "BEV/VCS world-space view was checked but no artifact path is cited"
    row["feature_results"][0]["candidate_adjudications"] = [candidate]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=11; OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15",
        candidate_evidence_packets=(_candidate_packet(),),
        feature_evidence_packets=(),
    )

    with pytest.raises(ReviewResultLoadError, match="bev_observation must cite the actual"):
        filter_results_for_packages(results, {package.package_id}, packages=[package])


def test_filter_results_for_packages_accepts_candidate_only_when_all_plane_artifacts_are_cited(tmp_path):
    row = _review_row()
    row["feature_results"][0]["triggered_issue_types"] = []
    row["feature_results"][0]["result"] = "pass"
    row["feature_results"][0]["candidate_adjudications"] = [
        _with_artifact_citations(_candidate_adjudication())
    ]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=11; OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15",
        candidate_evidence_packets=(_candidate_packet(),),
        feature_evidence_packets=(),
    )

    filtered = filter_results_for_packages(results, {package.package_id}, packages=[package])

    assert filtered[package.package_id].feature_results[0].candidate_adjudications[0].result == "cleared"


def test_load_review_results_rejects_bbox_dup_issue_without_quantitative_bev_evidence(tmp_path):
    row = _review_row()
    row["feature_results"][0]["triggered_issue_types"] = ["DEF-OD-BBOX-DUP"]
    candidate = _candidate_adjudication(result="issue")
    candidate["observed_evidence"] = (
        "raw frame has one visible target; QV overlay has overlapping boxes; "
        "BEV/VCS also looks close; JSON reports OD_bbox_overlap_candidates"
    )
    candidate["inference"] = "candidate is an issue because the image boxes overlap"
    candidate["decision_reason"] = "candidate is an issue because the image boxes overlap"
    row["feature_results"][0]["candidate_adjudications"] = [candidate]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="quantitative BEV/VCS world-space evidence"):
        load_review_results(path)


def test_load_review_results_rejects_candidate_missing_bev_observation(tmp_path):
    row = _review_row()
    row["feature_results"][0]["candidate_adjudications"] = [_candidate_adjudication()]
    row["feature_results"][0]["candidate_adjudications"][0]["bev_observation"] = ""
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="bev_observation is required"):
        load_review_results(path)


def test_filter_results_for_packages_accepts_large_bbox_candidate_issue_with_trigger(tmp_path):
    row = _review_row()
    row["feature_results"][0]["triggered_issue_types"] = ["DEF-OD-BBOX-FIT"]
    row["feature_results"][0]["candidate_adjudications"] = [
        {
            "candidate_id": "OD_BBOX_FIT_LARGE_60",
            "feature": "OD",
            "issue_type": "DEF-OD-BBOX-FIT",
            "object_ids": ["60"],
            "result": "issue",
            "checked_planes": ["raw", "ics", "bev_vcs", "json"],
            "raw_observation": "raw frame shows object id 60.",
            "ics_observation": "ICS/QV overlay has a large bbox for object id 60.",
            "bev_observation": "BEV/VCS grid is checked for object id 60.",
            "json_observation": "JSON reports OD_large_bbox_candidates=60.",
            "decision_reason": "OD_BBOX_FIT_LARGE_60 is an issue for object id 60.",
            "summary": "OD_BBOX_FIT_LARGE_60 was checked for object id 60.",
            "observed_evidence": "raw frame shows object id 60; QV overlay has a large bbox; BEV/VCS and JSON report OD_large_bbox_candidates=60",
            "inference": "OD_BBOX_FIT_LARGE_60 is an issue for object id 60.",
            "uncertainty": "single-frame review",
        }
    ]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=8; OD_large_bbox_candidates=60:w=0.30,h=0.51,area=0.15",
    )

    filtered = filter_results_for_packages(results, {package.package_id}, packages=[package])

    adjudication = filtered[package.package_id].feature_results[0].candidate_adjudications[0]
    assert adjudication.candidate_id == "OD_BBOX_FIT_LARGE_60"
    assert adjudication.result == "issue"


def test_filter_results_for_packages_accepts_low_road_edge_candidate_issue_with_trigger(tmp_path):
    row = _review_row()
    row["feature_results"].append(
        {
            "feature": "RBD",
            "result": "fail",
            "confidence": "high",
            "evaluated_issue_types": _evaluated_ids("RBD"),
            "triggered_issue_types": ["DEF-LD-RBD-FN"],
            "summary": "RBD low road edge count was checked.",
            "observed_evidence": "raw frame shows road edges; QV overlay shows a missing boundary; BEV/VCS grid shows under-covered edge coverage; JSON has RBD_low_road_edge_count=1/expected_min=2",
            "inference": "RBD fails for missing road edge.",
            "uncertainty": "single-frame review",
            "candidate_adjudications": [
                {
                    "candidate_id": "RBD_LOW_ROAD_EDGE_COUNT_1_OF_2",
                    "feature": "RBD",
                    "issue_type": "DEF-LD-RBD-FN",
                    "object_ids": [],
                    "result": "issue",
                    "checked_planes": ["raw", "ics", "bev_vcs", "json"],
                    "raw_observation": "raw frame shows two road edges.",
                    "ics_observation": "ICS/QV overlay shows a missing boundary.",
                    "bev_observation": "BEV/VCS grid is checked for road edge coverage.",
                    "json_observation": "JSON reports RBD_low_road_edge_count=1/expected_min=2.",
                    "decision_reason": "RBD_LOW_ROAD_EDGE_COUNT_1_OF_2 is an issue.",
                    "summary": "RBD_LOW_ROAD_EDGE_COUNT_1_OF_2 was checked.",
                    "observed_evidence": "raw frame shows two road edges; QV overlay, BEV/VCS grid, and JSON report RBD_low_road_edge_count=1/expected_min=2",
                    "inference": "RBD_LOW_ROAD_EDGE_COUNT_1_OF_2 is an issue.",
                    "uncertainty": "single-frame review",
                }
            ],
        }
    )
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=8; road_edges=1; RBD_low_road_edge_count=1/expected_min=2",
    )

    filtered = filter_results_for_packages(results, {package.package_id}, packages=[package])

    rbd = next(feature for feature in filtered[package.package_id].feature_results if feature.feature == "RBD")
    assert rbd.candidate_adjudications[0].candidate_id == "RBD_LOW_ROAD_EDGE_COUNT_1_OF_2"
    assert rbd.candidate_adjudications[0].result == "issue"


def test_filter_results_for_packages_rejects_issue_candidate_without_triggered_issue(tmp_path):
    row = _review_row()
    row["feature_results"][0]["triggered_issue_types"] = []
    row["feature_results"][0]["candidate_adjudications"] = [_candidate_adjudication(result="issue")]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")
    results = load_review_results(path)
    package = SimpleNamespace(
        package_id="CASE_001__frame_00000100",
        json_summary="objects=11; OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15",
    )

    with pytest.raises(ReviewResultLoadError, match="is issue but DEF-OD-BBOX-DUP is not triggered"):
        filter_results_for_packages(results, {package.package_id}, packages=[package])


def test_filter_results_for_packages_rejects_unresolved_machine_candidate(tmp_path):
    row = _review_row()
    row["feature_results"][0]["result"] = "fail"
    row["feature_results"][0]["triggered_issue_types"] = []
    row["feature_results"][0]["candidate_adjudications"] = [
        _candidate_adjudication(result="needs_review")
    ]
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="result must be one of: issue, cleared"):
        load_review_results(path)


def test_load_review_results_rejects_feature_needs_review(tmp_path):
    row = _review_row()
    row["feature_results"][0]["result"] = "needs_review"
    path = tmp_path / "llm_review_results.json"
    path.write_text(json.dumps({"results": [row]}), encoding="utf-8")

    with pytest.raises(ReviewResultLoadError, match="result must be pass or fail"):
        load_review_results(path)
