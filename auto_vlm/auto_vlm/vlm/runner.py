"""Feature-level VLM review runner and response merge helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auto_vlm.vlm.providers import FeatureReviewProvider


FEATURES = ("OD", "LD", "RBD", "TS", "TL")


@dataclass(frozen=True)
class FeatureRunSummary:
    tasks_total: int
    responses_total: int
    retryable_failures: tuple[dict[str, str], ...] = ()
    non_retryable_failures: tuple[dict[str, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "tasks_total": self.tasks_total,
            "responses_total": self.responses_total,
            "retryable_failures": list(self.retryable_failures),
            "non_retryable_failures": list(self.non_retryable_failures),
        }


def run_feature_reviews(
    tasks_root: str | Path,
    responses_root: str | Path,
    provider: FeatureReviewProvider,
    *,
    only_package: str | None = None,
    only_feature: str | None = None,
    retry_failed: bool = False,
) -> FeatureRunSummary:
    """Execute feature tasks one at a time and write response artifacts."""
    task_paths = _task_paths(Path(tasks_root), only_package=only_package, only_feature=only_feature)
    response_root = Path(responses_root)
    response_root.mkdir(parents=True, exist_ok=True)
    responses_total = 0
    retryable: list[dict[str, str]] = []
    non_retryable: list[dict[str, str]] = []

    for task_path in task_paths:
        try:
            task = json.loads(task_path.read_text(encoding="utf-8"))
            if not isinstance(task, dict):
                raise ValueError("task JSON must be an object")
            package_id = str(task["package_id"])
            feature = str(task["feature"])
            output_path = response_root / package_id / f"{feature}.json"
            if retry_failed and output_path.exists():
                existing = json.loads(output_path.read_text(encoding="utf-8"))
                if isinstance(existing, dict) and existing.get("validation_status") == "valid":
                    continue
            response = provider.review_feature(task)
            response.setdefault("package_id", package_id)
            response.setdefault("feature", feature)
            response.setdefault("reviewed_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")
            responses_total += 1
        except (FileNotFoundError, TimeoutError) as exc:
            retryable.append(_failure(task_path, exc))
        except Exception as exc:  # noqa: BLE001 - provider boundary records failures as artifacts.
            non_retryable.append(_failure(task_path, exc))

    return FeatureRunSummary(
        tasks_total=len(task_paths),
        responses_total=responses_total,
        retryable_failures=tuple(retryable),
        non_retryable_failures=tuple(non_retryable),
    )


def merge_feature_responses(
    responses_root: str | Path,
    output_path: str | Path,
    package_ids: list[str],
) -> Path:
    """Merge per-feature responses into llm_review_results.json format."""
    root = Path(responses_root)
    rows: list[dict[str, Any]] = []
    for package_id in package_ids:
        feature_results: list[dict[str, Any]] = []
        for feature in FEATURES:
            response_path = root / package_id / f"{feature}.json"
            if not response_path.exists():
                continue
            response = json.loads(response_path.read_text(encoding="utf-8"))
            if not isinstance(response, dict):
                raise ValueError(f"feature response must be an object: {response_path}")
            response.setdefault("feature", feature)
            response.pop("package_id", None)
            feature_results.append(response)
        if feature_results:
            rows.append({"package_id": package_id, "feature_results": feature_results})

    merged_path = Path(output_path)
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path.write_text(
        json.dumps({"artifact_version": "feature_review_results_v1", "results": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return merged_path


def _task_paths(root: Path, *, only_package: str | None, only_feature: str | None) -> list[Path]:
    if only_package:
        package_dirs = [root / only_package]
    else:
        package_dirs = sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []
    paths: list[Path] = []
    for package_dir in package_dirs:
        features = (only_feature.upper(),) if only_feature else FEATURES
        for feature in features:
            task_path = package_dir / f"{feature}.json"
            if task_path.exists():
                paths.append(task_path)
    return paths


def _failure(task_path: Path, exc: BaseException) -> dict[str, str]:
    return {
        "task_path": str(task_path),
        "error": str(exc),
    }
