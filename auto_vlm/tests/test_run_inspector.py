from __future__ import annotations

import json

from auto_vlm.pipeline.run_inspector import format_run_inspection, inspect_run_dir


def _write_manifest(run_dir):
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "counts": {"packages": 1, "review_results": 1, "errors": 0},
                "review_quality": {
                    "status": "passed",
                },
                "stages": [
                    {"name": "cross_feature_audit", "status": "accepted", "facts": {}},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_inspect_run_requires_review_artifact_for_final_report(tmp_path):
    _write_manifest(tmp_path)
    (tmp_path / "result.xlsx").write_text("xlsx", encoding="utf-8")
    (tmp_path / "summary.html").write_text("html", encoding="utf-8")
    (tmp_path / "review_tasks.json").write_text("{}", encoding="utf-8")

    inspection = inspect_run_dir(tmp_path)

    assert inspection.is_final_ready is False
    assert inspection.missing_artifacts == ("llm_review_results",)
    assert "llm_review_results: MISSING" in format_run_inspection(inspection)


def test_inspect_run_reports_required_artifacts_and_fail_rows(tmp_path):
    _write_manifest(tmp_path)
    (tmp_path / "result.xlsx").write_text("xlsx", encoding="utf-8")
    (tmp_path / "summary.html").write_text("html", encoding="utf-8")
    (tmp_path / "review_tasks.json").write_text("{}", encoding="utf-8")
    (tmp_path / "llm_review_results.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "package_id": "PKG_SYNTHETIC_FAIL",
                        "feature_results": [
                            {
                                "feature": "FEATURE_X",
                                "result": "fail",
                                "triggered_issue_types": [
                                    "ISSUE_A",
                                    "ISSUE_B",
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    inspection = inspect_run_dir(tmp_path)
    text = format_run_inspection(inspection)

    assert inspection.is_final_ready is True
    assert "final_ready: true" in text
    assert "cross_feature_audit_status: accepted" in text
    assert "llm_review_results.json" in text
    assert "PKG_SYNTHETIC_FAIL | FEATURE_X | ISSUE_A,ISSUE_B" in text


def test_inspect_run_requires_accepted_cross_feature_audit(tmp_path):
    _write_manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"][0]["status"] = "conflict"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "result.xlsx").write_text("xlsx", encoding="utf-8")
    (tmp_path / "summary.html").write_text("html", encoding="utf-8")
    (tmp_path / "review_tasks.json").write_text("{}", encoding="utf-8")
    (tmp_path / "llm_review_results.json").write_text(json.dumps({"results": []}), encoding="utf-8")

    inspection = inspect_run_dir(tmp_path)

    assert inspection.cross_feature_audit_status == "conflict"
    assert inspection.is_final_ready is False
