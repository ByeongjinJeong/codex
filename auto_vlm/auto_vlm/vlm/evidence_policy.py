"""Issue-type evidence-plane strategy for VLM review.

This module does not decide pass/fail. It tells the reviewer which evidence
plane is likely to expose an issue first and which plane must confirm it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IssueEvidenceStrategy:
    issue_type: str
    primary_discovery: str
    confirmation: str
    review_order: tuple[str, ...]
    must_not: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "issue_type": self.issue_type,
            "primary_discovery": self.primary_discovery,
            "confirmation": self.confirmation,
            "review_order": list(self.review_order),
            "must_not": list(self.must_not),
        }

    def as_text(self) -> str:
        return (
            f"{self.issue_type} | primary_discovery: {self.primary_discovery} | "
            f"confirmation: {self.confirmation} | review_order: {' -> '.join(self.review_order)}"
        )


def strategy_for_issue_type(issue_type: str) -> IssueEvidenceStrategy:
    """Return the evidence-plane strategy for a canonical DEF-* issue id."""
    issue = issue_type.upper()

    if "BBOX-DUP" in issue:
        return IssueEvidenceStrategy(
            issue_type=issue_type,
            primary_discovery="ICS/QV overlap cue plus BEV/VCS physical separation or overlap",
            confirmation=(
                "Confirm with raw object identity and BEV/VCS extents. Image overlap alone is not enough."
            ),
            review_order=("raw", "ics", "bev_vcs", "json"),
            must_not=("Do not mark duplicate from ICS overlap unless BEV/VCS also supports same-object duplication.",),
        )
    if "BBOX-FIT" in issue:
        return IssueEvidenceStrategy(
            issue_type=issue_type,
            primary_discovery="raw object shape against ICS/QV bbox/projection",
            confirmation="Confirm with BEV/VCS placement and JSON bbox/object values where visible.",
            review_order=("raw", "ics", "bev_vcs", "json"),
            must_not=("Do not clear or fail only from large image coverage; near-field objects can be large.",),
        )
    if any(token in issue for token in ("HEADING", "DIST", "RANGE", "LOCALIZATION", "ROLE", "COEFF")):
        return IssueEvidenceStrategy(
            issue_type=issue_type,
            primary_discovery="BEV/VCS geometry and JSON spatial values",
            confirmation="Confirm the BEV/VCS suspicion against raw scene semantics and ICS/QV projection.",
            review_order=("raw_context", "bev_vcs", "json", "ics"),
            must_not=("Do not require the issue to be obvious in ICS before checking BEV/VCS.",),
        )
    if any(token in issue for token in ("FN", "FP")):
        return IssueEvidenceStrategy(
            issue_type=issue_type,
            primary_discovery="raw visible scene compared with ICS/QV rendered presence/absence",
            confirmation="Use BEV/VCS and JSON existence/range to confirm whether output is missing or extra.",
            review_order=("raw", "ics", "bev_vcs", "json"),
            must_not=("Do not clear because one plane looks acceptable while another plane shows missing/extra output.",),
        )
    if any(token in issue for token in ("CLASS", "TYPE", "STATE", "COLOR", "SHAPE", "MOTION")):
        return IssueEvidenceStrategy(
            issue_type=issue_type,
            primary_discovery="raw appearance and ICS/QV label/state rendering",
            confirmation="Confirm with JSON class/state/type values and BEV/VCS placement when relevant.",
            review_order=("raw", "ics", "json", "bev_vcs"),
            must_not=("Do not use BEV geometry alone to decide semantic class/state.",),
        )
    if any(token in issue for token in ("ID", "UPDATE", "DATA")):
        return IssueEvidenceStrategy(
            issue_type=issue_type,
            primary_discovery="JSON tracking/update fields and frame-range continuity when available",
            confirmation="Confirm visible target continuity with raw/ICS/BEV; single-frame evidence is limited.",
            review_order=("json", "raw", "ics", "bev_vcs"),
            must_not=("Do not overclaim temporal ID/update failures from a single frame.",),
        )
    return IssueEvidenceStrategy(
        issue_type=issue_type,
        primary_discovery="raw, ICS/QV, BEV/VCS, and JSON cross-check",
        confirmation="Confirm with at least two relevant evidence planes before triggering the issue.",
        review_order=("raw", "ics", "bev_vcs", "json"),
        must_not=("Do not decide from one evidence plane when other planes are readable.",),
    )


def strategies_for_issue_types(issue_types: tuple[str, ...] | list[str]) -> tuple[IssueEvidenceStrategy, ...]:
    return tuple(strategy_for_issue_type(issue_type) for issue_type in issue_types)
