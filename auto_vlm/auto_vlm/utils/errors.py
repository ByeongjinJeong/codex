"""Structured errors used across adapters, engine, and reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolError:
    code: str
    problem: str
    location: str
    cause: str
    fix: str
    case_id: str | None = None
    case_status: str = "tool_error"
    batch_status: str = "continue"

    def as_message(self) -> str:
        return "\n".join(
            [
                f"problem: {self.problem}",
                f"location: {self.location}",
                f"cause: {self.cause}",
                f"fix: {self.fix}",
                f"case_status: {self.case_status}",
                f"batch_status: {self.batch_status}",
            ]
        )
