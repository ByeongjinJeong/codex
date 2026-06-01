"""Structured review obligations derived from compact JSON summary hints."""

from __future__ import annotations

import re
from dataclasses import dataclass


REQUIRED_CANDIDATE_PLANES = frozenset({"raw", "ics", "bev_vcs", "json"})


@dataclass(frozen=True)
class ReviewCandidateObligation:
    candidate_id: str
    feature: str
    issue_type: str
    object_ids: tuple[str, ...]
    source: str


def obligations_from_json_summary(json_summary: str | None) -> tuple[ReviewCandidateObligation, ...]:
    """Return candidate-level obligations encoded in a package json_summary."""
    if not json_summary:
        return ()

    obligations: list[ReviewCandidateObligation] = []
    for pair in _od_bbox_overlap_pairs(json_summary):
        left, right = pair
        obligations.append(
            ReviewCandidateObligation(
                candidate_id=f"OD_BBOX_DUP_{left}_{right}",
                feature="OD",
                issue_type="DEF-OD-BBOX-DUP",
                object_ids=(left, right),
                source="OD_bbox_overlap_candidates",
            )
        )
    for object_id in _od_large_bbox_ids(json_summary):
        obligations.append(
            ReviewCandidateObligation(
                candidate_id=f"OD_BBOX_FIT_LARGE_{object_id}",
                feature="OD",
                issue_type="DEF-OD-BBOX-FIT",
                object_ids=(object_id,),
                source="OD_large_bbox_candidates",
            )
        )
    low_road_edge = _rbd_low_road_edge_count(json_summary)
    if low_road_edge is not None:
        observed, expected = low_road_edge
        obligations.append(
            ReviewCandidateObligation(
                candidate_id=f"RBD_LOW_ROAD_EDGE_COUNT_{observed}_OF_{expected}",
                feature="RBD",
                issue_type="DEF-LD-RBD-FN",
                object_ids=(),
                source="RBD_low_road_edge_count",
            )
        )
    return tuple(obligations)


def _od_bbox_overlap_pairs(json_summary: str) -> list[tuple[str, str]]:
    match = re.search(r"OD_bbox_overlap_candidates=([^;]+)", json_summary)
    if not match:
        return []

    pairs: list[tuple[str, str]] = []
    for item in match.group(1).split(","):
        candidate_match = re.match(r"\s*([^-:,;\s]+)-([^-:,;\s]+):", item)
        if not candidate_match:
            continue
        pairs.append((candidate_match.group(1), candidate_match.group(2)))
    return pairs


def _od_large_bbox_ids(json_summary: str) -> list[str]:
    match = re.search(r"OD_large_bbox_candidates=([^;]+)", json_summary)
    if not match:
        return []

    object_ids: list[str] = []
    for item in match.group(1).split(","):
        candidate_match = re.match(r"\s*([^:,;\s]+):", item)
        if not candidate_match:
            continue
        object_ids.append(candidate_match.group(1))
    return object_ids


def _rbd_low_road_edge_count(json_summary: str) -> tuple[str, str] | None:
    match = re.search(r"RBD_low_road_edge_count=([^/\s;]+)/expected_min=([^;\s]+)", json_summary)
    if not match:
        return None
    return match.group(1), match.group(2)
