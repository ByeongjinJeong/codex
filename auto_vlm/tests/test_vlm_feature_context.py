from __future__ import annotations

from pathlib import Path

import pytest

from auto_vlm.vlm.feature_context import build_feature_review_contexts
from auto_vlm.vlm.reference_context import (
    ISSUE_REFERENCE_FILES,
    canonical_issue_type_ids,
    gtless_single_frame_applicability,
)


def test_focus_feature_builds_common_and_matching_feature_context():
    contexts = build_feature_review_contexts("LD")

    assert [context.feature.value for context in contexts] == ["LD"]
    assert "docs/references/adas_vision_review_workflow.md" in contexts[0].reference_sources
    assert "docs/references/regression_issue_types/common.md" in contexts[0].reference_sources
    assert "docs/references/regression_issue_types/ld.md" in contexts[0].reference_sources
    assert any("host_lanes" in item for item in contexts[0].inspection_checklist)


def test_focus_feature_can_select_multiple_contexts():
    contexts = build_feature_review_contexts("OD,RBD")

    assert [context.feature.value for context in contexts] == ["OD", "RBD"]


def test_all_focus_builds_active_feature_contexts():
    contexts = build_feature_review_contexts("ALL")

    assert [context.feature.value for context in contexts] == ["OD", "LD", "RBD", "TS", "TL"]
    for context in contexts:
        assert any("raw" in item.lower() for item in context.inspection_checklist)
        assert any("ICS" in item or "BEV" in item for item in context.inspection_checklist)
        assert any("ICS/image overlay looks correct" in item for item in context.must_not)


def test_feature_context_rejects_unsupported_feature():
    with pytest.raises(ValueError):
        build_feature_review_contexts("CALIB")


def test_rbd_context_uses_rbd_reference_file():
    context = build_feature_review_contexts("RBD")[0]

    assert "docs/references/regression_issue_types/rbd.md" in context.reference_sources
    assert any("road_edges" in item for item in context.inspection_checklist)


def test_od_context_forces_full_issue_type_scan():
    context = build_feature_review_contexts("OD")[0]

    assert any("DEF-OD-HEADING" in item for item in context.inspection_checklist)
    assert any("DEF-OD-BBOX-DUP" in item for item in context.inspection_checklist)
    assert any("BEV/world-space" in item and "ICS" in item for item in context.inspection_checklist)
    assert any("DEF-OD-HEADING" in item for item in context.issue_type_guidance)
    assert any("DEF-OD-BBOX-DUP" in item for item in context.issue_type_guidance)


def test_each_active_context_requires_every_md_defined_issue_type_before_pass():
    contexts = build_feature_review_contexts("ALL")

    for context in contexts:
        assert any("every" in item.lower() and "issue type" in item.lower() for item in context.inspection_checklist)
        reference_path = ISSUE_REFERENCE_FILES[context.feature]
        expected_definitions = _definition_headings(reference_path)
        for definition in expected_definitions:
            assert any(definition in item for item in context.inspection_checklist)


def test_each_active_feature_has_canonical_issue_types():
    contexts = build_feature_review_contexts("ALL")

    for context in contexts:
        issue_ids = canonical_issue_type_ids(context.feature)
        assert issue_ids
        assert all(issue_id.startswith("DEF-") for issue_id in issue_ids)
        assert len(issue_ids) == len(set(issue_ids))


def test_each_active_feature_has_gtless_applicability_for_every_canonical_issue_type():
    contexts = build_feature_review_contexts("ALL")

    for context in contexts:
        issue_ids = set(canonical_issue_type_ids(context.feature))
        applicability = gtless_single_frame_applicability(context.feature)
        assert set(applicability) == issue_ids
        assert set(applicability.values()) <= {"direct", "limited", "not_evaluable"}


def test_each_canonical_issue_type_has_minimum_review_definition():
    contexts = build_feature_review_contexts("ALL")

    for context in contexts:
        sections = _definition_sections(ISSUE_REFERENCE_FILES[context.feature])
        assert sections
        for heading, lines in sections.items():
            section_text = "\n".join(lines)
            assert "Definition:" in section_text, heading
            assert any(
                marker in section_text
                for marker in ("Review focus:", "Key signal:", "Key signals:", "Key values:")
            ), heading


def _definition_headings(path: Path) -> list[str]:
    headings: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("### DEF-"):
            headings.append(stripped.lstrip("#").strip())
    return headings


def _definition_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_heading = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("### DEF-"):
            current_heading = stripped.lstrip("#").strip()
            sections[current_heading] = [stripped]
            continue
        if stripped.startswith("### ") and current_heading:
            current_heading = ""
        if current_heading:
            sections[current_heading].append(stripped)
    return sections
