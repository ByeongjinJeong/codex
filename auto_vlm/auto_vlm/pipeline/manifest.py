"""Run manifest generation for Auto VLM batches."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_vlm.models.evidence import FrameEvidencePackage
from auto_vlm.models.results import PackageReviewResult
from auto_vlm.utils.errors import ToolError
from auto_vlm.vlm.review_validator import ReviewQualityReport, empty_review_quality_report


def write_run_manifest(
    path: str | Path,
    *,
    input_path: str | Path,
    output_dir: str | Path,
    packages: list[FrameEvidencePackage],
    errors: list[ToolError],
    result_xlsx: Path | None,
    summary_html: Path | None,
    review_tasks_json: Path | None,
    review_results_json: Path | None,
    review_results: dict[str, PackageReviewResult],
    review_quality: ReviewQualityReport | None = None,
    reuse_existing_artifacts: bool = False,
    reused_artifact_packages: int = 0,
    generated_artifact_packages: int = 0,
) -> Path:
    """Write a machine-readable manifest for one batch run."""
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_run_manifest(
        input_path=input_path,
        output_dir=output_dir,
        packages=packages,
        errors=errors,
        result_xlsx=result_xlsx,
        summary_html=summary_html,
        review_tasks_json=review_tasks_json,
        review_results_json=review_results_json,
        review_results=review_results,
        review_quality=review_quality,
        reuse_existing_artifacts=reuse_existing_artifacts,
        reused_artifact_packages=reused_artifact_packages,
        generated_artifact_packages=generated_artifact_packages,
    )
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def build_run_manifest(
    *,
    input_path: str | Path,
    output_dir: str | Path,
    packages: list[FrameEvidencePackage],
    errors: list[ToolError],
    result_xlsx: Path | None,
    summary_html: Path | None,
    review_tasks_json: Path | None,
    review_results_json: Path | None,
    review_results: dict[str, PackageReviewResult],
    review_quality: ReviewQualityReport | None = None,
    reuse_existing_artifacts: bool = False,
    reused_artifact_packages: int = 0,
    generated_artifact_packages: int = 0,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    review_quality = review_quality or empty_review_quality_report()
    report_paths = {
        "result_xlsx": _path_value(result_xlsx),
        "summary_html": _path_value(summary_html),
    }
    error_rows = [_error_as_dict(error) for error in errors]

    return {
        "manifest_version": "run_manifest_v1",
        "run_id": output_root.name,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "config": {
            "adapter": "excel",
            "no_vlm_provider_calls": True,
            "reuse_existing_artifacts": reuse_existing_artifacts,
        },
        "inputs": {
            "input_path": str(Path(input_path)),
            "review_results_json": _path_value(review_results_json),
        },
        "outputs": {
            "output_dir": str(output_root),
            "reports": report_paths,
            "manifest_json": str(output_root / "manifest.json"),
            "review_tasks_json": _path_value(review_tasks_json),
        },
        "counts": {
            "packages": len(packages),
            "review_results": len(review_results),
            "errors": len(errors),
            "cases": len({package.case_id for package in packages}),
        },
        "stages": [
            _stage("input", "completed", {"cases_with_packages": len({package.case_id for package in packages})}),
            _stage(
                "evidence",
                "completed" if packages else "failed",
                {
                    "packages": len(packages),
                    "reused_artifact_packages": reused_artifact_packages,
                    "generated_artifact_packages": generated_artifact_packages,
                },
            ),
            _stage(
                "review_tasks",
                "completed" if review_tasks_json else "pending",
                {"review_tasks_json": _path_value(review_tasks_json)},
            ),
            _stage(
                "review_results",
                "completed" if review_results_json else "pending",
                {"review_results": len(review_results)},
            ),
            _stage(
                "review_quality",
                review_quality.status,
                {
                    "errors": len(review_quality.errors),
                    "warnings": len(review_quality.warnings),
                },
            ),
            _stage(
                "reports",
                _report_stage_status(result_xlsx, summary_html, review_results, review_quality),
                report_paths,
            ),
        ],
        "packages": [
            {
                "package_id": package.package_id,
                "case_id": package.case_id,
                "sampled_frame": package.sampled_frame,
                "focus_feature": package.focus_feature,
                "sampling_mode": package.sampling_mode,
            }
            for package in packages
        ],
        "review_provenance": _review_provenance_summary(review_results),
        "review_quality": review_quality.as_dict(),
        "errors": error_rows,
    }


def _stage(name: str, status: str, facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "facts": facts,
    }


def _report_stage_status(
    result_xlsx: Path | None,
    summary_html: Path | None,
    review_results: dict[str, PackageReviewResult],
    review_quality: ReviewQualityReport,
) -> str:
    if result_xlsx and summary_html:
        return "completed"
    if not review_results:
        return "pending_review"
    return "failed"


def _review_provenance_summary(results: dict[str, PackageReviewResult]) -> dict[str, Any]:
    sources = Counter(result.provenance.source.value for result in results.values())
    reviewers = sorted({result.provenance.reviewer for result in results.values() if result.provenance.reviewer})
    providers = sorted({result.provenance.provider for result in results.values() if result.provenance.provider})
    models = sorted({result.provenance.model for result in results.values() if result.provenance.model})
    prompt_versions = sorted(
        {result.provenance.prompt_version for result in results.values() if result.provenance.prompt_version}
    )
    artifact_versions = sorted(
        {result.provenance.artifact_version for result in results.values() if result.provenance.artifact_version}
    )
    return {
        "total": len(results),
        "sources": dict(sorted(sources.items())),
        "reviewers": reviewers,
        "providers": providers,
        "models": models,
        "prompt_versions": prompt_versions,
        "artifact_versions": artifact_versions,
    }


def _error_as_dict(error: ToolError) -> dict[str, str | None]:
    return {
        "code": error.code,
        "case_id": error.case_id,
        "problem": error.problem,
        "location": error.location,
        "cause": error.cause,
        "fix": error.fix,
        "case_status": error.case_status,
        "batch_status": error.batch_status,
    }


def _path_value(path: Path | None) -> str | None:
    return str(path) if path else None
