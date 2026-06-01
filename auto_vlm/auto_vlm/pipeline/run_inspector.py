"""Run directory inspection for final workbook reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_ARTIFACTS = (
    ("llm_review_results", "llm_review_results.json"),
    ("result_xlsx", "result.xlsx"),
    ("summary_html", "summary.html"),
    ("manifest_json", "manifest.json"),
    ("review_tasks", "review_tasks.json"),
)


@dataclass(frozen=True)
class RunInspection:
    run_dir: Path
    manifest: dict[str, Any]
    artifacts: dict[str, Path | None]
    missing_artifacts: tuple[str, ...]
    fail_rows: tuple[tuple[str, str, str], ...]

    @property
    def packages(self) -> int:
        return int(self.manifest.get("counts", {}).get("packages", 0))

    @property
    def review_results(self) -> int:
        return int(self.manifest.get("counts", {}).get("review_results", 0))

    @property
    def errors(self) -> int:
        return int(self.manifest.get("counts", {}).get("errors", 0))

    @property
    def review_quality_status(self) -> str:
        return str(self.manifest.get("review_quality", {}).get("status", "unknown"))

    @property
    def is_final_ready(self) -> bool:
        return (
            self.packages > 0
            and self.errors == 0
            and self.review_results == self.packages
            and self.review_quality_status == "passed"
            and not self.missing_artifacts
        )


def inspect_run_dir(run_dir: str | Path) -> RunInspection:
    root = Path(run_dir)
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"manifest.json not found or unreadable: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest.json is malformed: {manifest_path}: {exc}") from exc

    artifacts: dict[str, Path | None] = {}
    missing: list[str] = []
    for key, filename in REQUIRED_ARTIFACTS:
        path = root / filename
        artifacts[key] = path if path.exists() else None
        if not path.exists():
            missing.append(key)

    return RunInspection(
        run_dir=root,
        manifest=manifest,
        artifacts=artifacts,
        missing_artifacts=tuple(missing),
        fail_rows=_fail_rows(root / "llm_review_results.json"),
    )


def format_run_inspection(inspection: RunInspection) -> str:
    lines = [
        f"run_dir: {inspection.run_dir}",
        "required_artifacts:",
    ]
    for key, _filename in REQUIRED_ARTIFACTS:
        path = inspection.artifacts[key]
        lines.append(f"  {key}: {path if path else 'MISSING'}")
    lines.extend(
        [
            "status:",
            f"  packages: {inspection.packages}",
            f"  review_results: {inspection.review_results}",
            f"  errors: {inspection.errors}",
            f"  review_quality_status: {inspection.review_quality_status}",
            f"  final_ready: {str(inspection.is_final_ready).lower()}",
            "fail_rows:",
        ]
    )
    if inspection.fail_rows:
        for package_id, feature, issue_types in inspection.fail_rows:
            lines.append(f"  {package_id} | {feature} | {issue_types}")
    else:
        lines.append("  none")
    return "\n".join(lines)


def _fail_rows(path: Path) -> tuple[tuple[str, str, str], ...]:
    if not path.exists():
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    rows = data.get("results", data)
    if not isinstance(rows, list):
        return ()

    fails: list[tuple[str, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        package_id = str(row.get("package_id", ""))
        feature_results = row.get("feature_results", [])
        if not isinstance(feature_results, list):
            continue
        for feature in feature_results:
            if not isinstance(feature, dict) or feature.get("result") != "fail":
                continue
            issue_types = feature.get("triggered_issue_types", [])
            if not isinstance(issue_types, list):
                issue_types = []
            fails.append(
                (
                    package_id,
                    str(feature.get("feature", "")),
                    ",".join(str(item) for item in issue_types),
                )
            )
    return tuple(fails)
