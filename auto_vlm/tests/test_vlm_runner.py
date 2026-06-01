from __future__ import annotations

import json

from auto_vlm.vlm.providers import ManualResponseProvider
from auto_vlm.vlm.runner import merge_feature_responses, run_feature_reviews


def test_manual_feature_runner_writes_response_artifact(tmp_path):
    tasks_root = tmp_path / "model" / "tasks"
    responses_root = tmp_path / "model" / "responses"
    manual_root = tmp_path / "manual"
    package_id = "CASE_001__frame_00000100"
    task_dir = tasks_root / package_id
    manual_dir = manual_root / package_id
    task_dir.mkdir(parents=True)
    manual_dir.mkdir(parents=True)
    (task_dir / "OD.json").write_text(
        json.dumps({"package_id": package_id, "feature": "OD"}),
        encoding="utf-8",
    )
    (manual_dir / "OD.json").write_text(
        json.dumps(
            {
                "result": "pass",
                "confidence": "medium",
                "evaluated_issue_types": ["DEF-OD-FN"],
                "triggered_issue_types": [],
                "summary": "OD pass",
                "observed_evidence": "raw/QV/BEV/JSON",
                "inference": "pass",
                "uncertainty": "none",
            }
        ),
        encoding="utf-8",
    )

    summary = run_feature_reviews(tasks_root, responses_root, ManualResponseProvider(manual_root), only_feature="OD")

    assert summary.tasks_total == 1
    assert summary.responses_total == 1
    response = json.loads((responses_root / package_id / "OD.json").read_text(encoding="utf-8"))
    assert response["package_id"] == package_id
    assert response["feature"] == "OD"


def test_merge_feature_responses_preserves_package_result_shape(tmp_path):
    package_id = "CASE_001__frame_00000100"
    response_dir = tmp_path / "responses" / package_id
    response_dir.mkdir(parents=True)
    for feature in ("OD", "LD"):
        (response_dir / f"{feature}.json").write_text(
            json.dumps(
                {
                    "package_id": package_id,
                    "feature": feature,
                    "result": "pass",
                    "confidence": "medium",
                    "evaluated_issue_types": [f"DEF-{feature}-DUMMY"],
                    "triggered_issue_types": [],
                    "summary": f"{feature} pass",
                    "observed_evidence": "raw/QV/BEV/JSON",
                    "inference": "pass",
                    "uncertainty": "none",
                }
            ),
            encoding="utf-8",
        )

    output = merge_feature_responses(tmp_path / "responses", tmp_path / "llm_review_results.json", [package_id])
    data = json.loads(output.read_text(encoding="utf-8"))

    assert data["artifact_version"] == "feature_review_results_v1"
    assert data["results"][0]["package_id"] == package_id
    assert [item["feature"] for item in data["results"][0]["feature_results"]] == ["OD", "LD"]
