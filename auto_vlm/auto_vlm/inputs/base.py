"""Base adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from auto_vlm.models.cases import EvaluationCase
from auto_vlm.utils.errors import ToolError


@dataclass(frozen=True)
class AdapterResult:
    cases: list[EvaluationCase] = field(default_factory=list)
    errors: list[ToolError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
