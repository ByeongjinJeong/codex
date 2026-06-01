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
                        "package_id": "CASE_002__frame_00000235",
                        "feature_results": [
                            {
                                "feature": "RBD",
                                "result": "fail",
                                "triggered_issue_types": [
                                    "DEF-LD-RBD-FN",
                                    "DEF-LD-RBD-RANGE",
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
    assert "llm_review_results.json" in text
    assert "CASE_002__frame_00000235 | RBD | DEF-LD-RBD-FN,DEF-LD-RBD-RANGE" in text
