"""Reference excerpt loading for VLM feature review context."""

from __future__ import annotations

from pathlib import Path

from auto_vlm.models.vlm import Feature


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_DIR = PROJECT_ROOT / "docs" / "references"
ISSUE_TYPES_DIR = REFERENCES_DIR / "regression_issue_types"
QV_REFERENCE = REFERENCES_DIR / "qualification_visualizer_output_info.md"
ADAS_WORKFLOW_REFERENCE = REFERENCES_DIR / "adas_vision_review_workflow.md"
REVIEW_APPLICABILITY_REFERENCE = ISSUE_TYPES_DIR / "review_applicability.md"

ISSUE_REFERENCE_FILES = {
    Feature.OD: ISSUE_TYPES_DIR / "od.md",
    Feature.LD: ISSUE_TYPES_DIR / "ld.md",
    Feature.RBD: ISSUE_TYPES_DIR / "rbd.md",
    Feature.TS: ISSUE_TYPES_DIR / "ts.md",
    Feature.TL: ISSUE_TYPES_DIR / "tl.md",
}

QV_SECTION_HEADINGS = {
    Feature.OD: [
        "## 12. Output Information Summary for Auto VLM Use",
        "### 13.2 Object Identity and Role Values",
        "### 13.3 Object Class and Motion Values",
        "### 13.4 Object Position and Size Values",
        "### 13.5 Image-Space Object Values",
        "## 14. How to Combine Values Without Issue Assumptions",
    ],
    Feature.LD: [
        "## 12. Output Information Summary for Auto VLM Use",
        "### 13.6 Lane and Road Edge Values",
        "### 13.7 CPP and INTP Values",
        "## 14. How to Combine Values Without Issue Assumptions",
    ],
    Feature.RBD: [
        "## 12. Output Information Summary for Auto VLM Use",
        "### 13.6 Lane and Road Edge Values",
        "### 13.7 CPP and INTP Values",
        "## 14. How to Combine Values Without Issue Assumptions",
    ],
    Feature.TS: [
        "## 12. Output Information Summary for Auto VLM Use",
        "### 13.8 Traffic Sign Values",
        "## 14. How to Combine Values Without Issue Assumptions",
    ],
    Feature.TL: [
        "## 12. Output Information Summary for Auto VLM Use",
        "### 13.9 Traffic Light Values",
        "## 14. How to Combine Values Without Issue Assumptions",
    ],
}


def load_qv_json_interpretation(feature: Feature) -> list[str]:
    text = _read_reference(QV_REFERENCE)
    excerpts: list[str] = []
    for heading in QV_SECTION_HEADINGS[feature]:
        excerpts.extend(_summarize_markdown(_extract_section(text, heading), max_lines=8))
    return _dedupe(excerpts)


def load_issue_type_guidance(feature: Feature) -> list[str]:
    common = _read_reference(ISSUE_TYPES_DIR / "common.md")
    feature_text = _read_reference(ISSUE_REFERENCE_FILES[feature])
    return _dedupe(
        _summarize_markdown(common, max_lines=12)
        + _summarize_markdown(feature_text, max_lines=12)
        + _extract_issue_definition_summaries(common)
        + _extract_issue_definition_summaries(feature_text)
    )


def load_issue_type_scan_checklist(feature: Feature) -> list[str]:
    """Build an issue scan checklist from the feature reference DEF-* sections."""
    definitions = canonical_issue_type_headings(feature)
    if not definitions:
        return [f"Evaluate every {feature.value} issue type defined in the reference before assigning pass."]
    return [
        f"Evaluate every {feature.value} issue type defined in the reference before assigning pass.",
        *(f"Check {definition}." for definition in definitions),
        f"Only clear {feature.value} as pass after every listed DEF-* issue type has been considered against raw/QV/JSON evidence.",
    ]


def load_adas_common_workflow() -> list[str]:
    """Return the common ADAS review workflow lines."""
    text = _read_reference(ADAS_WORKFLOW_REFERENCE)
    return _summarize_markdown(_extract_section(text, "## Common 3-Plane Workflow"), max_lines=12)


def load_adas_feature_checklist(feature: Feature) -> list[str]:
    """Return feature-specific ADAS review checklist lines."""
    text = _read_reference(ADAS_WORKFLOW_REFERENCE)
    return _summarize_markdown(_extract_section(text, f"### {feature.value}"), max_lines=8)


def load_adas_must_not() -> list[str]:
    """Return ADAS review prohibitions from the workflow reference."""
    text = _read_reference(ADAS_WORKFLOW_REFERENCE)
    return _summarize_markdown(_extract_section(text, "## Must Not"), max_lines=10)


def canonical_issue_type_ids(feature: Feature) -> tuple[str, ...]:
    """Return the feature's canonical DEF-* ids from its reference document."""
    ids = []
    for heading in canonical_issue_type_headings(feature):
        issue_id = heading.split(":", 1)[0].strip()
        if issue_id:
            ids.append(issue_id)
    return tuple(ids)


def canonical_issue_type_headings(feature: Feature) -> tuple[str, ...]:
    """Return the feature's canonical DEF-* headings from its reference document."""
    feature_text = _read_reference(ISSUE_REFERENCE_FILES[feature])
    return tuple(_extract_issue_definition_headings(feature_text))


def gtless_single_frame_applicability(feature: Feature) -> dict[str, str]:
    """Return canonical issue type applicability for GT-less single-frame review."""
    rows = _load_review_applicability_rows()
    result = {
        issue_id: status
        for row_feature, issue_id, status in rows
        if row_feature == feature.value
    }
    canonical = set(canonical_issue_type_ids(feature))
    missing = sorted(canonical - set(result))
    if missing:
        raise ValueError(
            f"review applicability is missing {feature.value} issue type(s): {', '.join(missing)}"
        )
    extra = sorted(set(result) - canonical)
    if extra:
        raise ValueError(
            f"review applicability has unknown {feature.value} issue type(s): {', '.join(extra)}"
        )
    return result


def reference_sources_for(feature: Feature) -> list[str]:
    return [
        _relative_source(ADAS_WORKFLOW_REFERENCE),
        _relative_source(QV_REFERENCE),
        _relative_source(ISSUE_TYPES_DIR / "common.md"),
        _relative_source(ISSUE_REFERENCE_FILES[feature]),
        _relative_source(REVIEW_APPLICABILITY_REFERENCE),
    ]


def _read_reference(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"reference file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def _relative_source(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _extract_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return ""

    heading_level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.startswith("#"):
            continue
        level = len(line) - len(line.lstrip("#"))
        if level <= heading_level:
            end = index
            break
    return "\n".join(lines[start:end])


def _summarize_markdown(text: str, max_lines: int) -> list[str]:
    selected: list[str] = []
    in_fence = False
    pending_bullet = ""

    def flush_pending() -> None:
        nonlocal pending_bullet
        if pending_bullet:
            selected.append(pending_bullet.strip())
            pending_bullet = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if line.startswith("#"):
            flush_pending()
            selected.append(line.lstrip("#").strip())
        elif line.startswith("-"):
            flush_pending()
            pending_bullet = line.lstrip("- ").strip()
        elif pending_bullet:
            pending_bullet = f"{pending_bullet} {line}"
        elif in_fence or ":" in line:
            selected.append(line.lstrip("- ").strip())
        if len(selected) >= max_lines:
            break
    if len(selected) < max_lines:
        flush_pending()
    return selected


def _extract_issue_definition_summaries(text: str) -> list[str]:
    """Return compact summaries for every DEF-* issue section in a reference file."""
    lines = text.splitlines()
    summaries: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("### DEF-"):
            continue

        heading_level = len(stripped) - len(stripped.lstrip("#"))
        section_end = len(lines)
        for next_index in range(index + 1, len(lines)):
            next_line = lines[next_index].strip()
            if not next_line.startswith("#"):
                continue
            next_level = len(next_line) - len(next_line.lstrip("#"))
            if next_level <= heading_level:
                section_end = next_index
                break

        summaries.extend(_summarize_issue_definition_section(lines[index:section_end]))
    return summaries


def _extract_issue_definition_headings(text: str) -> list[str]:
    headings: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("### DEF-"):
            headings.append(line.lstrip("#").strip())
    return headings


def _load_review_applicability_rows() -> list[tuple[str, str, str]]:
    text = _read_reference(REVIEW_APPLICABILITY_REFERENCE)
    rows: list[tuple[str, str, str]] = []
    in_table = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "```text":
            in_table = True
            continue
        if line == "```" and in_table:
            break
        if not in_table or not line or line.startswith("feature |"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 4:
            continue
        feature, issue_id, status = parts[:3]
        if status not in {"direct", "limited", "not_evaluable"}:
            raise ValueError(f"unsupported review applicability status for {issue_id}: {status}")
        rows.append((feature, issue_id, status))
    return rows


def _summarize_issue_definition_section(lines: list[str]) -> list[str]:
    heading = lines[0].lstrip("#").strip()
    summary = [heading]
    capture_next = False
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            continue
        if line in {"Definition:", "Split:", "Key signal:", "Key signals:", "Key values:", "Review focus:"}:
            summary.append(line)
            capture_next = True
            continue
        if capture_next and (line.startswith("-") or ":" in line):
            summary.append(line.lstrip("- ").strip())
            if len(summary) >= 6:
                break
    return summary


def _dedupe(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        result.append(line)
    return result
