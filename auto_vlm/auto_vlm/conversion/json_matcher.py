"""Frame JSON matching and compact summary generation."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_vlm.models.evidence import EvidenceIntegrity, JsonFrameMatchStatus, JsonParseStatus


@dataclass(frozen=True)
class JsonMatchResult:
    json_snippet: Path | None
    json_summary: str
    evidence_integrity: EvidenceIntegrity


def match_frame_json(
    json_dir: str | Path | None,
    sampled_frame: int,
    output_dir: str | Path,
    focus_feature: str = "ALL",
) -> JsonMatchResult:
    if json_dir is None:
        return JsonMatchResult(
            json_snippet=None,
            json_summary="json unavailable",
            evidence_integrity=EvidenceIntegrity(
                json_available=False,
                json_frame_match_status=JsonFrameMatchStatus.MISSING_JSON_DIR,
                json_parse_status=JsonParseStatus.MISSING,
                integrity_notes=("json_dir was not provided",),
            ),
        )

    source_dir = Path(json_dir)
    if not source_dir.exists():
        return JsonMatchResult(
            json_snippet=None,
            json_summary="json unavailable",
            evidence_integrity=EvidenceIntegrity(
                json_available=False,
                json_frame_match_status=JsonFrameMatchStatus.MISSING_JSON_DIR,
                json_parse_status=JsonParseStatus.MISSING,
                integrity_notes=(f"json_dir does not exist: {source_dir}",),
            ),
        )

    source_path = source_dir / f"{sampled_frame:08d}.json"
    if not source_path.exists():
        return JsonMatchResult(
            json_snippet=None,
            json_summary="frame json missing",
            evidence_integrity=EvidenceIntegrity(
                json_available=True,
                json_frame_match_status=JsonFrameMatchStatus.MISSING_FRAME_JSON,
                json_parse_status=JsonParseStatus.MISSING,
                integrity_notes=(f"frame json not found: {source_path.name}",),
            ),
        )

    output_path = Path(output_dir) / f"frame_{sampled_frame:08d}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, output_path)

    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return JsonMatchResult(
            json_snippet=output_path,
            json_summary="frame json malformed",
            evidence_integrity=EvidenceIntegrity(
                json_available=True,
                json_frame_match_status=JsonFrameMatchStatus.EXACT,
                json_parse_status=JsonParseStatus.MALFORMED,
                integrity_notes=(f"json parse error: {exc.msg}",),
            ),
        )

    offset_suspected = _frame_id_mismatch(data, sampled_frame)
    notes = (f"json frame_id differs from sampled frame {sampled_frame}",) if offset_suspected else ()
    return JsonMatchResult(
        json_snippet=output_path,
        json_summary=summarize_frame_json(data, focus_feature=focus_feature),
        evidence_integrity=EvidenceIntegrity(
            json_available=True,
            json_frame_match_status=JsonFrameMatchStatus.EXACT,
            json_parse_status=JsonParseStatus.OK,
            json_offset_suspected=offset_suspected,
            integrity_notes=notes,
        ),
    )


def summarize_frame_json(data: dict[str, Any], focus_feature: str = "ALL") -> str:
    counts = {
        "objects": _qv_count(data, "avi_objects", "VIS_OBJ_Element")
        or _count_any(data, ["objects", "object", "object_list", "detected_objects"]),
        "lanes": _qv_count(data, "avi_lanes_host", "VIS_LH_Element")
        or _count_any(data, ["lanes", "lane", "lane_list"]),
        "road_edges": _qv_count(data, "avi_lanes_road_edge", "VIS_LRE_Element")
        or _count_any(data, ["road_edges", "road_edge", "road_boundaries"]),
        "signs": _qv_count(data, "avi_traffic_signs", "VIS_TSR_Element")
        or _count_any(data, ["traffic_signs", "signs", "tsr"]),
        "lights": _qv_count(data, "avi_traffic_lights", "VIS_TFL_Element")
        or _count_any(data, ["traffic_lights", "lights", "tlr"]),
        "markings": _qv_count(data, "avi_road_markings", "VIS_RMD_Element")
        or _count_any(data, ["road_markings", "markings", "rmd"]),
    }
    parts = [f"{key}={value}" for key, value in counts.items()]

    frame_id = _find_first_key(data, ["frame_id", "frameId", "frame", "frame_number"])
    if frame_id is not None:
        parts.insert(0, f"frame_id={frame_id}")

    abnormal = _collect_status_hints(data)
    if abnormal:
        parts.append("status=" + ",".join(abnormal[:5]))

    feature_hint = _feature_specific_hint(data, focus_feature)
    if feature_hint:
        parts.append(feature_hint)

    return "; ".join(parts)


def _count_any(data: Any, names: list[str]) -> int:
    matches = []
    _collect_named_values(data, set(names), matches)
    total = 0
    for value in matches:
        if isinstance(value, list):
            total += len(value)
        elif isinstance(value, dict):
            total += len(value)
        elif value is not None:
            total += 1
    return total


def _qv_count(data: dict[str, Any], section_name: str, element_name: str) -> int:
    section = data.get(section_name)
    if not isinstance(section, dict):
        return 0
    element = section.get(element_name)
    return len(element) if isinstance(element, list) else 0


def _collect_named_values(data: Any, names: set[str], matches: list[Any]) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if key in names:
                matches.append(value)
            _collect_named_values(value, names, matches)
    elif isinstance(data, list):
        for item in data:
            _collect_named_values(item, names, matches)


def _find_first_key(data: Any, names: list[str]) -> Any:
    if isinstance(data, dict):
        for name in names:
            if name in data:
                return data[name]
        for value in data.values():
            found = _find_first_key(value, names)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_first_key(item, names)
            if found is not None:
                return found
    return None


def _collect_status_hints(data: Any) -> list[str]:
    hints: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(token in key_lower for token in ("failsafe", "calib", "status", "error")):
                if isinstance(value, (dict, list)):
                    pass
                elif value not in (None, "", 0, "0", "ok", "OK", "normal", "NORMAL"):
                    hints.append(f"{key}={value}")
            hints.extend(_collect_status_hints(value))
    elif isinstance(data, list):
        for item in data:
            hints.extend(_collect_status_hints(item))
    return hints


def _feature_specific_hint(data: dict[str, Any], focus_feature: str) -> str:
    feature = (focus_feature or "ALL").upper()
    if feature == "OD":
        classes = _collect_values_by_key(data, ["class", "class_name", "type"])[:8]
        return "OD_classes=" + ",".join(map(str, classes)) if classes else ""
    if feature in {"LD", "RBD"}:
        lane_ids = _collect_values_by_key(data, ["track_id", "lane_id", "id"])[:8]
        return f"{feature}_ids=" + ",".join(map(str, lane_ids)) if lane_ids else ""
    if feature in {"TS", "TL"}:
        states = _collect_values_by_key(data, ["sign_name", "struct_state", "state"])[:8]
        return f"{feature}_states=" + ",".join(map(str, states)) if states else ""
    return ""


def _collect_values_by_key(data: Any, names: list[str]) -> list[Any]:
    values: list[Any] = []
    names_set = set(names)
    if isinstance(data, dict):
        for key, value in data.items():
            if key in names_set and not isinstance(value, (dict, list)):
                values.append(value)
            values.extend(_collect_values_by_key(value, names))
    elif isinstance(data, list):
        for item in data:
            values.extend(_collect_values_by_key(item, names))
    return values


def _frame_id_mismatch(data: dict[str, Any], sampled_frame: int) -> bool:
    frame_id = _find_first_key(data, ["frame_id", "frameId", "frame", "frame_number"])
    if frame_id is None:
        return False
    try:
        return int(frame_id) != sampled_frame
    except (TypeError, ValueError):
        return False
