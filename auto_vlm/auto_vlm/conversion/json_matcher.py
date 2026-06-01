"""Frame JSON matching and compact summary generation."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_vlm.models.cases import normalize_review_features
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

    od_hints = _od_issue_hints(data)
    parts.extend(od_hints)
    rbd_hints = _rbd_issue_hints(counts)
    parts.extend(rbd_hints)

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
    features = _selected_focus_features(focus_feature)
    hints = []
    if "OD" in features:
        classes = _collect_values_by_key(data, ["class", "class_name", "type"])[:8]
        if classes:
            hints.append("OD_classes=" + ",".join(map(str, classes)))
    for feature in ("LD", "RBD"):
        if feature in features:
            lane_ids = _collect_values_by_key(data, ["track_id", "lane_id", "id"])[:8]
            if lane_ids:
                hints.append(f"{feature}_ids=" + ",".join(map(str, lane_ids)))
    for feature in ("TS", "TL"):
        if feature not in features:
            continue
        states = _collect_values_by_key(data, ["sign_name", "struct_state", "state"])[:8]
        if states:
            hints.append(f"{feature}_states=" + ",".join(map(str, states)))
    return "; ".join(hints)


def _selected_focus_features(focus_feature: str) -> set[str]:
    normalized = normalize_review_features(focus_feature)
    if normalized == "ALL":
        return {"OD", "LD", "RBD", "TS", "TL"}
    return set(normalized.split(","))


def _od_issue_hints(data: dict[str, Any]) -> list[str]:
    objects = _qv_objects(data)
    if not objects:
        return []

    hints: list[str] = []
    heading_samples = []
    for obj in objects[:8]:
        obj_id = obj.get("VIS_OBJ_ID")
        physical = obj.get("VIS_OBJ_Physical_State")
        motion = obj.get("VIS_OBJ_Motion_State")
        if not isinstance(physical, dict) or not isinstance(motion, dict):
            continue
        heading = physical.get("Heading")
        orientation = motion.get("Motion_Orientation")
        if obj_id is not None and heading is not None and orientation is not None:
            heading_samples.append(f"{obj_id}:{_round_float(heading)}/o{orientation}")
    if heading_samples:
        hints.append("OD_heading_samples=" + ",".join(heading_samples))

    overlap_candidates = _od_bbox_overlap_candidates(objects)
    if overlap_candidates:
        hints.append("OD_bbox_overlap_candidates=" + ",".join(overlap_candidates[:5]))
    large_bbox_candidates = _od_large_bbox_candidates(objects)
    if large_bbox_candidates:
        hints.append("OD_large_bbox_candidates=" + ",".join(large_bbox_candidates[:5]))
    return hints


def _rbd_issue_hints(counts: dict[str, int]) -> list[str]:
    """Return compact RBD cues that need visual adjudication."""
    road_edges = counts.get("road_edges", 0)
    lanes = counts.get("lanes", 0)
    if lanes > 0 and road_edges < 2:
        return [f"RBD_low_road_edge_count={road_edges}/expected_min=2"]
    return []


def _qv_objects(data: dict[str, Any]) -> list[dict[str, Any]]:
    section = data.get("avi_objects")
    if not isinstance(section, dict):
        return []
    objects = section.get("VIS_OBJ_Element")
    if not isinstance(objects, list):
        return []
    return [item for item in objects if isinstance(item, dict)]


def _od_bbox_overlap_candidates(objects: list[dict[str, Any]]) -> list[str]:
    boxes = _od_image_boxes(objects)
    candidates: list[str] = []
    for index, left in enumerate(boxes):
        for right in boxes[index + 1 :]:
            overlap_area = _intersection_area(left["box"], right["box"])
            if overlap_area <= 0:
                continue
            smaller_area = min(left["area"], right["area"])
            union_area = left["area"] + right["area"] - overlap_area
            min_overlap = overlap_area / smaller_area if smaller_area else 0.0
            iou = overlap_area / union_area if union_area else 0.0
            if not ((min_overlap >= 0.45 and iou >= 0.05) or iou >= 0.25):
                continue
            candidates.append(
                f"{left['id']}-{right['id']}:min_overlap={min_overlap:.2f},iou={iou:.2f}"
            )
    return candidates


def _od_large_bbox_candidates(objects: list[dict[str, Any]]) -> list[str]:
    """Return object ids whose image box is unusually large for a single-frame check."""
    boxes = _od_image_boxes(objects)
    if not boxes:
        return []

    max_x = max(box["box"][2] for box in boxes)
    max_y = max(box["box"][3] for box in boxes)
    frame_area = max_x * max_y
    if frame_area <= 0:
        return []

    candidates: list[str] = []
    for box in boxes:
        x0, y0, x1, y1 = box["box"]
        width = x1 - x0
        height = y1 - y0
        area_ratio = box["area"] / frame_area
        width_ratio = width / max_x if max_x else 0.0
        height_ratio = height / max_y if max_y else 0.0
        if area_ratio < 0.12 and width_ratio < 0.30 and height_ratio < 0.45:
            continue
        candidates.append(
            f"{box['id']}:w={width_ratio:.2f},h={height_ratio:.2f},area={area_ratio:.2f}"
        )
    return candidates


def _od_image_boxes(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    boxes = []
    for obj in objects:
        coords = obj.get("VIS_OBJ_Image_Coordinates")
        if not isinstance(coords, dict):
            continue
        xs = [value for key, value in coords.items() if key.endswith("_X") and isinstance(value, (int, float))]
        ys = [value for key, value in coords.items() if key.endswith("_Y") and isinstance(value, (int, float))]
        if not xs or not ys:
            continue
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        if width <= 0 or height <= 0:
            continue
        boxes.append(
            {
                "id": obj.get("VIS_OBJ_ID"),
                "class": obj.get("VIS_OBJ_Object_Class"),
                "box": (min(xs), min(ys), max(xs), max(ys)),
                "area": width * height,
            }
        )
    return boxes


def _intersection_area(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def _round_float(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return str(value)
    return f"{value:.2f}"


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
