"""Provider boundaries for feature-level review execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class FeatureReviewProvider(Protocol):
    """Executes one package + feature review task."""

    name: str

    def review_feature(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return one structured feature review response."""


@dataclass(frozen=True)
class ManualResponseProvider:
    """Loads pre-authored feature responses from a directory.

    The directory must use the same contract as provider output:
    <responses_root>/<package_id>/<feature>.json.
    """

    responses_root: Path
    name: str = "manual"

    def review_feature(self, task: dict[str, Any]) -> dict[str, Any]:
        package_id = _required_text(task, "package_id")
        feature = _required_text(task, "feature")
        response_path = self.responses_root / package_id / f"{feature}.json"
        try:
            data = json.loads(response_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise FileNotFoundError(f"manual feature response not found: {response_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"manual feature response is malformed: {response_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"manual feature response must be an object: {response_path}")
        return data


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"feature task missing required text field: {key}")
    return value.strip()
