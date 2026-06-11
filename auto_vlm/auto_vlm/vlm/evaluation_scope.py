"""Evaluation scope annotations for VLM review packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VEHICLE_CLASSES = frozenset({"car", "vehicle", "truck", "bus", "van"})
VRU_CLASSES = frozenset({"pedestrian", "ped", "bicycle", "bike", "byc", "cyclist", "motorcycle", "motorbike"})
OD_SCOPE_RULES = {
    "vehicle_max_long_distance_m": 100.0,
    "vru_max_long_distance_m": 70.0,
}


def build_evaluation_scope(json_snippet: str | Path | None) -> dict[str, Any]:
    """Build non-decisive scope annotations from JSON output.

    Scope annotations define which SW objects are inside the configured review
    range. They must not be used as proof that an issue exists.
    """
    data = _load_json(json_snippet)
    od_objects = _od_scope_objects(data)
    return {
        "version": "evaluation_scope_v1",
        "features": {
            "OD": {
                "status": "available" if data else "json_unavailable",
                "rules": dict(OD_SCOPE_RULES),
                "objects": od_objects,
                "summary": _scope_summary(od_objects),
                "usage": (
                    "Use these annotations only to decide whether an observed OD issue is "
                    "inside the configured evaluation range. Do not use them as evidence "
                    "that an issue exists. If raw evidence contradicts JSON class or "
                    "distance, treat scope as uncertain."
                ),
            }
        },
    }


def _load_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _od_scope_objects(data: dict[str, Any]) -> list[dict[str, Any]]:
    objects = _qv_objects(data) or _generic_objects(data)
    scoped = [_scope_od_object(obj) for obj in objects]
    return [item for item in scoped if item is not None]


def _qv_objects(data: dict[str, Any]) -> list[dict[str, Any]]:
    section = data.get("avi_objects")
    if not isinstance(section, dict):
        return []
    objects = section.get("VIS_OBJ_Element")
    if not isinstance(objects, list):
        return []
    return [item for item in objects if isinstance(item, dict)]


def _generic_objects(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("objects", "object_list", "detected_objects"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _scope_od_object(obj: dict[str, Any]) -> dict[str, Any] | None:
    object_id = _first_present(obj, ("VIS_OBJ_ID", "id", "object_id", "track_id"))
    object_class = _normalize_class(_first_present(obj, ("VIS_OBJ_Object_Class", "class", "class_name", "type")))
    long_distance = _long_distance(obj)
    category = _scope_category(object_class)

    if object_id is None and object_class == "unknown" and long_distance is None:
        return None

    if category == "vehicle":
        limit = OD_SCOPE_RULES["vehicle_max_long_distance_m"]
    elif category == "vru":
        limit = OD_SCOPE_RULES["vru_max_long_distance_m"]
    else:
        limit = None

    if category == "unknown":
        scope = "scope_uncertain"
        reason = "class unknown; do not exclude by scope"
    elif long_distance is None:
        scope = "scope_uncertain"
        reason = "long_distance unavailable; do not exclude by scope"
    elif abs(long_distance) <= float(limit):
        scope = "in_scope"
        reason = f"{category} within {limit:.0f}m"
    else:
        scope = "out_of_scope"
        reason = f"{category} beyond {limit:.0f}m"

    return {
        "object_id": "" if object_id is None else str(object_id),
        "class": object_class,
        "category": category,
        "long_distance_m": long_distance,
        "scope": scope,
        "reason": reason,
    }


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _normalize_class(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized or "unknown"
    return str(value).strip().lower() or "unknown"


def _scope_category(object_class: str) -> str:
    if object_class in VEHICLE_CLASSES:
        return "vehicle"
    if object_class in VRU_CLASSES:
        return "vru"
    return "unknown"


def _long_distance(obj: dict[str, Any]) -> float | None:
    for key in ("long_distance", "Long_Distance", "distance", "range"):
        value = obj.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    physical = obj.get("VIS_OBJ_Physical_State")
    if isinstance(physical, dict):
        value = physical.get("Long_Distance")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _scope_summary(objects: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"in_scope": 0, "out_of_scope": 0, "scope_uncertain": 0}
    for obj in objects:
        scope = obj.get("scope")
        if scope in counts:
            counts[scope] += 1
    return counts
