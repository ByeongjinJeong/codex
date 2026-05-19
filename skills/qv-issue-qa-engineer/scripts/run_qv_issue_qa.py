#!/usr/bin/env python3
"""LLM final QA review for QV batch issue Excel outputs.

The script prepares QV-native frame context for each issue row, asks Codex CLI to
write a structured result JSON file, then builds a reviewer-friendly Excel.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time
import tempfile
from copy import copy
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MODE = "uncertain-only"
DEFAULT_LLM_PRIORITY_MAX = 2
VALID_DECISIONS = {"실제 이슈", "우선순위 낮은 이슈", "이슈 아님", "판단 보류"}
VALID_MODES = {"all", "uncertain-only"}
VALID_GUIDANCE_MODES = {"full", "focused"}


def _is_nan(v: Any) -> bool:
    return isinstance(v, float) and math.isnan(v)


def _clean(v: Any) -> Any:
    if _is_nan(v):
        return None
    return v


def _to_float(v: Any) -> float | None:
    try:
        f = float(v)
    except Exception:
        return None
    return f if math.isfinite(f) else None


def _to_int(v: Any) -> int | None:
    try:
        return int(float(v))
    except Exception:
        return None


def _fmt_num(v: Any, digits: int = 2) -> str:
    f = _to_float(v)
    if f is None:
        return "-"
    text = f"{f:.{digits}f}"
    return text.rstrip("0").rstrip(".")


def _contains_any(text: Any, needles: tuple[str, ...]) -> bool:
    value = str(text or "").lower()
    return any(needle in value for needle in needles)


def _issue_signal_label(issue: dict[str, Any]) -> str:
    original_signal = str(issue.get("problem_signal") or "").strip()
    if original_signal and original_signal.lower() not in {"reason", "issue"}:
        return original_signal
    rule = str(issue.get("rule") or "").upper()
    issue_type = str(issue.get("issue_type") or "").lower()
    feature = str(issue.get("feature") or "").lower()
    if "TTC" in rule or "ttc" in issue_type or "ttc" in feature:
        return "TTC / inverse TTC"
    if "HEADING" in rule or "heading" in issue_type or "heading" in feature:
        return "Heading change"
    if "DIST" in rule or "distance" in issue_type or "distance" in feature:
        return "Longitudinal / lateral distance"
    if "VEL" in rule or "velocity" in issue_type or "velocity" in feature:
        return "Absolute velocity"
    if "ID" in rule or "track" in issue_type:
        return "Tracking continuity"
    return str(issue.get("problem_signal") or "")


def _find_repo_root(start_path: Path) -> Path | None:
    cur = start_path.resolve()
    for p in [cur] + list(cur.parents):
        if (p / "utils" / "data_processor_fvc.py").exists():
            return p
    return None


@lru_cache(maxsize=1)
def _load_qv_parser(repo_root_str: str):
    repo_root = Path(repo_root_str)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from utils.data_processor_fvc import parse_single_fvc_frame  # type: ignore

    return parse_single_fvc_frame


def _find_json_path(log_path: Path, frame: int) -> Path | None:
    candidates = [log_path / f"{frame:08d}.json", log_path / f"{frame}.json"]
    for p in candidates:
        if p.exists():
            return p
    if not log_path.exists() or not log_path.is_dir():
        return None
    matched = sorted(log_path.glob(f"*{frame}*.json"))
    return matched[0] if matched else None


def _json_lookup_status(log_path: Path, frame: int) -> dict[str, Any]:
    if not log_path.exists():
        return {"status": "log_path_not_found", "used_path": "", "expected": []}
    if not log_path.is_dir():
        return {"status": "log_path_not_directory", "used_path": "", "expected": []}
    expected = [str(log_path / f"{frame:08d}.json"), str(log_path / f"{frame}.json")]
    found = _find_json_path(log_path, frame)
    if found:
        return {"status": "found", "used_path": str(found), "expected": expected}
    return {"status": "frame_json_not_found", "used_path": "", "expected": expected}


def _qv_frame_snapshot(repo_root: Path, log_path: Path, frame_i: int) -> dict[str, Any] | None:
    try:
        parser = _load_qv_parser(str(repo_root))
        return parser(str(log_path), int(frame_i))
    except Exception:
        return None


def _match_object_id(obj: dict[str, Any], object_id: Any) -> bool:
    oid = obj.get("id", obj.get("VIS_OBJ_ID"))
    if oid is None or object_id is None:
        return False
    try:
        return int(float(oid)) == int(float(object_id))
    except Exception:
        return str(oid) == str(object_id)


def _object_snapshot(frame_data: dict[str, Any] | None, object_id: Any) -> dict[str, Any] | None:
    if not frame_data:
        return None
    objs = frame_data.get("objects") or frame_data.get("OD") or []
    if not objs:
        objs = ((frame_data.get("avi_objects") or {}).get("VIS_OBJ_Element") or [])
    target = None
    for obj in objs:
        if _match_object_id(obj, object_id):
            target = obj
            break
    if not target:
        return None

    if "id" in target:
        inv_ttc = _to_float(target.get("inv_ttc"))
        ttc = None if not inv_ttc else abs(1.0 / inv_ttc)
        return {
            "id": target.get("id"),
            "class": target.get("class"),
            "age": target.get("age"),
            "existence_prob": target.get("existence_prob"),
            "lane_assignment": target.get("lane_assignment"),
            "motion_status": target.get("motion_status"),
            "motion_category": target.get("motion_category"),
            "inv_ttc": target.get("inv_ttc"),
            "ttc_from_inv_ttc": ttc,
            "long_dist": target.get("long_dist"),
            "lat_dist": target.get("lat_dist"),
            "rel_long_vel": target.get("rel_long_vel"),
            "rel_lat_vel": target.get("rel_lat_vel"),
            "abs_long_vel": target.get("abs_long_vel"),
            "abs_lat_vel": target.get("abs_lat_vel"),
            "width": target.get("width"),
            "length": target.get("length"),
            "heading": target.get("heading"),
            "image_box_hint": {
                "front_bottom_left": [target.get("img_coord_front_bottom_left_x"), target.get("img_coord_front_bottom_left_y")],
                "front_top_right": [target.get("img_coord_front_top_right_x"), target.get("img_coord_front_top_right_y")],
                "back_bottom_left": [target.get("img_coord_back_bottom_left_x"), target.get("img_coord_back_bottom_left_y")],
                "back_top_right": [target.get("img_coord_back_top_right_x"), target.get("img_coord_back_top_right_y")],
            },
        }

    phys = target.get("VIS_OBJ_Physical_State") or {}
    motion = target.get("VIS_OBJ_Motion_State") or {}
    inv_ttc = _to_float(target.get("VIS_OBJ_InvTTC"))
    return {
        "id": target.get("VIS_OBJ_ID"),
        "class": target.get("VIS_OBJ_Object_Class"),
        "motion_status": motion.get("Motion_Status"),
        "inv_ttc": target.get("VIS_OBJ_InvTTC"),
        "ttc_from_inv_ttc": None if not inv_ttc else abs(1.0 / inv_ttc),
        "long_dist": phys.get("Long_Distance"),
        "lat_dist": phys.get("Lat_Distance"),
        "rel_long_vel": phys.get("Relative_Long_Velocity"),
        "rel_lat_vel": phys.get("Relative_Lat_Velocity"),
    }


def _build_context(repo_root: Path, log_path: Any, frame: Any, object_id: Any) -> dict[str, Any]:
    try:
        frame_i = int(frame)
    except Exception:
        return {"error": "invalid_frame", "frame": frame}

    lp = Path(str(log_path)) if log_path not in (None, "") else Path("")
    prev_status = _json_lookup_status(lp, frame_i - 1)
    curr_status = _json_lookup_status(lp, frame_i)
    next_status = _json_lookup_status(lp, frame_i + 1)

    prev_frame = _qv_frame_snapshot(repo_root, lp, frame_i - 1)
    curr_frame = _qv_frame_snapshot(repo_root, lp, frame_i)
    next_frame = _qv_frame_snapshot(repo_root, lp, frame_i + 1)
    curr_objects = (curr_frame or {}).get("objects") or []

    return {
        "parser": "utils.data_processor_fvc.parse_single_fvc_frame",
        "mapping_source": "utils/aptiv/aptiv_mapping_config.py",
        "frame_window": [frame_i - 1, frame_i, frame_i + 1],
        "json_files": {
            "previous": prev_status,
            "current": curr_status,
            "next": next_status,
        },
        "qv_header": {
            "obj_cipv_id": (curr_frame or {}).get("obj_cipv_id"),
            "obj_niv_l_id": (curr_frame or {}).get("obj_niv_l_id"),
            "obj_niv_r_id": (curr_frame or {}).get("obj_niv_r_id"),
            "obj_vd_cnt": (curr_frame or {}).get("obj_vd_cnt"),
            "obj_vru_cnt": (curr_frame or {}).get("obj_vru_cnt"),
            "com_highway_flag": (curr_frame or {}).get("com_highway_flag"),
            "com_road_type": (curr_frame or {}).get("com_road_type"),
            "com_region": (curr_frame or {}).get("com_region"),
            "is_highway": (curr_frame or {}).get("is_highway"),
            "vehicle_speed_kph": (curr_frame or {}).get("vehicle_speed") or (curr_frame or {}).get("speed") or (curr_frame or {}).get("V"),
        },
        "objects_count": len(curr_objects),
        "target_object_prev": _object_snapshot(prev_frame, object_id),
        "target_object_curr": _object_snapshot(curr_frame, object_id),
        "target_object_next": _object_snapshot(next_frame, object_id),
    }


def _resolve_image_path(row: pd.Series, input_excel: Path) -> tuple[Path | None, str, str]:
    shot = _clean(row.get("screenshot_path"))
    if isinstance(shot, str) and shot.strip():
        p = Path(shot)
        if p.exists():
            return p, "from_screenshot_path", ""

    image_dir = input_excel.parent / input_excel.stem
    if not image_dir.exists() or not image_dir.is_dir():
        return None, "image_folder_not_found", str(image_dir)

    frame_val = _clean(row.get("frame"))
    try:
        frame_i = int(frame_val)
    except Exception:
        frame_i = None

    rule = str(_clean(row.get("rule")) or "").replace(" ", "_")
    if frame_i is not None:
        pattern = f"*frame_{frame_i:08d}*{rule}*.jpg" if rule else f"*frame_{frame_i:08d}*.jpg"
        matches = sorted(image_dir.glob(pattern))
        if matches:
            return matches[0], "from_synced_folder_frame_rule", ""

    if isinstance(row.name, int):
        row_tag = f"row_{row.name + 2:04d}"
        matches = sorted(image_dir.glob(f"{row_tag}*.jpg"))
        if matches:
            return matches[0], "from_synced_folder_rowtag", ""

    return None, "image_not_found_for_row", str(image_dir)


def _issue_from_row(row: pd.Series) -> dict[str, Any]:
    cols = [
        "dataset",
        "yaml_index",
        "video_path",
        "log_path",
        "rule",
        "priority",
        "feature",
        "issue_type",
        "frame",
        "consecutive_frames",
        "object_id",
        "category",
        "role",
        "problem_signal",
        "current_value",
        "previous_value",
        "expected_value",
        "long_dist",
        "lat_dist",
        "ttc",
        "lidar_id",
        "lidar_name",
        "lidar_long",
        "lidar_lat",
        "reason",
        "screenshot_path",
        "issue_context_key",
        "issue_context_path",
    ]
    return {c: _clean(row.get(c)) for c in cols if c in row.index}


def _load_exported_issue_context(row: pd.Series, input_excel: Path) -> dict[str, Any] | None:
    path_value = _clean(row.get("issue_context_path"))
    candidates: list[Path] = []
    if isinstance(path_value, str) and path_value.strip():
        candidates.append(Path(path_value))
    candidates.append(input_excel.with_name(f"{input_excel.stem}_issue_context.json"))

    context_key = _clean(row.get("issue_context_key"))
    if not context_key and isinstance(row.name, int):
        context_key = f"row_{row.name + 2:04d}"

    for candidate in candidates:
        try:
            if not candidate.exists():
                continue
            document = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        issues = document.get("issues") or []
        matched = None
        for item in issues:
            if isinstance(item, dict) and item.get("context_key") == context_key:
                matched = item
                break
        if matched is None and isinstance(row.name, int) and 0 <= row.name < len(issues):
            maybe = issues[int(row.name)]
            matched = maybe if isinstance(maybe, dict) else None
        return {
            "context_path": str(candidate),
            "context_key": context_key,
            "qv_visualization_manifest": document.get("qv_visualization_manifest") or {},
            "issue_context": matched or {},
        }
    return None


def _issue_priority_score(issue: dict[str, Any]) -> int | None:
    return _to_int(issue.get("priority"))


def _compose_reason_text(parts: list[str]) -> str:
    cleaned = [str(p).strip().rstrip(".") for p in parts if str(p or "").strip()]
    if not cleaned:
        return ""
    return ". ".join(cleaned) + "."


def _signal_delta_summary(issue: dict[str, Any]) -> str:
    if "FN" in str(issue.get("rule") or "").upper() or "fn" in str(issue.get("issue_type") or "").lower():
        return ""
    long_dist = _to_float(issue.get("long_dist"))
    lat_dist = _to_float(issue.get("lat_dist"))
    lidar_long = _to_float(issue.get("lidar_long"))
    lidar_lat = _to_float(issue.get("lidar_lat"))
    current_v = _to_float(issue.get("current_value"))
    signal = str(issue.get("problem_signal") or "").lower()
    parts: list[str] = []
    if long_dist is not None and lidar_long is not None:
        parts.append(f"|ΔLong|={abs(long_dist - lidar_long):.2f}m")
    if lat_dist is not None and lidar_lat is not None:
        parts.append(f"|ΔLat|={abs(lat_dist - lidar_lat):.2f}m")
    if ("error" in signal or "dist" in signal or "vel" in signal) and current_v is not None:
        parts.append(f"Rule value={current_v:.2f}")
    return ", ".join(parts)


def _adas_priority_reason(
    priority: Any,
    role: Any,
    long_dist: float | None,
    abs_lat: float | None,
    ttc: float | None,
    signal_detail: dict[str, str],
    lane_relevant: bool,
) -> str:
    p = _to_int(priority)
    role_text = str(role or "-")
    distance_text = f"종거리 {_fmt_num(long_dist)}m, 횡거리 {_fmt_num(abs_lat)}m"
    ttc_text = f", TTC {_fmt_num(ttc)}s" if ttc is not None else ""
    if p is None:
        return f"{signal_detail['evidence_sentence']} ADAS/AD 제어 영향은 {distance_text}{ttc_text} 기준으로 추가 판단이 필요합니다."
    if p <= 2:
        return (
            f"{signal_detail['evidence_sentence']} Role={role_text}이고 {distance_text}{ttc_text}로 "
            "자차 경로 또는 근접 객체 영향 가능성이 있어 높은 우선순위로 산정했습니다."
        )
    if p == 3:
        return (
            f"{signal_detail['evidence_sentence']} {distance_text}{ttc_text} 기준으로 즉각적인 제어 영향은 제한적이나, "
            "perception 품질 확인이 필요한 중간 우선순위로 산정했습니다."
        )
    return (
        f"{signal_detail['evidence_sentence']} {distance_text}{ttc_text}이고 "
        "자차 주행 경로 영향성이 낮아 ADAS/AD 안전 영향 관점에서 낮은 우선순위로 산정했습니다."
    )


def _llm_need_reason_text(reasons: list[str], needs_llm: bool) -> str:
    if not needs_llm:
        return ""
    return _compose_reason_text(reasons or ["이미지/BEV 또는 경계 조건 확인이 필요해 LLM 검토 대상으로 분류했습니다"])


def _primary_signal_detail(issue: dict[str, Any]) -> dict[str, str]:
    rule = str(issue.get("rule") or "").upper()
    issue_type = str(issue.get("issue_type") or "").lower()
    signal = _issue_signal_label(issue)
    long_dist = _to_float(issue.get("long_dist"))
    lat_dist = _to_float(issue.get("lat_dist"))
    lidar_long = _to_float(issue.get("lidar_long"))
    lidar_lat = _to_float(issue.get("lidar_lat"))
    current_value = _to_float(issue.get("current_value"))

    if "FN" in rule or "fn" in issue_type:
        return {
            "primary_signal": "Lidar FN",
            "signal_value": f"Lidar ID={issue.get('lidar_id') or '-'}, name={issue.get('lidar_name') or '-'}",
            "delta_vs_lidar": "",
            "evidence_sentence": (
                f"LiDAR 객체(ID {issue.get('lidar_id') or '-'})가 기준 영역에 존재하지만 대응되는 OD/TS/TL 객체가 부족해 미검출 후보로 검출되었습니다."
            ),
        }

    long_error = abs(long_dist - lidar_long) if long_dist is not None and lidar_long is not None else None
    lat_error = abs(lat_dist - lidar_lat) if lat_dist is not None and lidar_lat is not None else None
    if signal.lower() in {"longitudinal / lateral distance", "longitudinal / lateral distance"}:
        if long_error is not None and (lat_error is None or long_error >= lat_error):
            signal = "Long Error"
            current_value = long_error
        elif lat_error is not None:
            signal = "Lat Error"
            current_value = lat_error

    delta_parts: list[str] = []
    if long_error is not None:
        delta_parts.append(f"Long 오차 {long_error:.2f}m")
    if lat_error is not None:
        delta_parts.append(f"Lat 오차 {lat_error:.2f}m")
    delta_text = ", ".join(delta_parts)

    if signal.lower().startswith("long") and long_dist is not None and lidar_long is not None:
        value_text = f"JSON long={long_dist:.2f}m, LiDAR long={lidar_long:.2f}m"
        evidence = f"종방향 거리 기준으로 JSON {long_dist:.2f}m와 LiDAR {lidar_long:.2f}m의 차이가 {abs(long_dist - lidar_long):.2f}m 발생했습니다."
    elif signal.lower().startswith(("lat", "lateral")) and lat_dist is not None and lidar_lat is not None:
        value_text = f"JSON lat={lat_dist:.2f}m, LiDAR lat={lidar_lat:.2f}m"
        evidence = f"횡방향 거리 기준으로 JSON {lat_dist:.2f}m와 LiDAR {lidar_lat:.2f}m의 차이가 {abs(lat_dist - lidar_lat):.2f}m 발생했습니다."
    else:
        value_text = _fmt_num(current_value) if current_value is not None else str(issue.get("current_value") or "-")
        evidence = f"{signal} 값 {value_text}로 룰 조건을 만족했습니다."

    return {
        "primary_signal": signal,
        "signal_value": value_text,
        "delta_vs_lidar": delta_text,
        "evidence_sentence": evidence,
    }


def _build_numeric_snapshot(issue: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    obj = context.get("target_object_curr") or {}
    issue_ttc = _to_float(issue.get("ttc"))
    obj_ttc = _to_float(obj.get("ttc_from_inv_ttc"))
    ttc = issue_ttc if issue_ttc is not None else obj_ttc
    issue_long = _to_float(issue.get("long_dist"))
    issue_lat = _to_float(issue.get("lat_dist"))
    obj_long = _to_float(obj.get("long_dist"))
    obj_lat = _to_float(obj.get("lat_dist"))
    long_dist = issue_long if issue_long is not None else obj_long
    lat_dist = issue_lat if issue_lat is not None else obj_lat
    abs_lat = abs(lat_dist) if lat_dist is not None else None
    existence_prob = _to_float(obj.get("existence_prob"))
    obj_id = _to_int(obj.get("id"))
    qv = context.get("qv_header") or {}
    qv_ids = {
        _to_int(qv.get("obj_cipv_id")),
        _to_int(qv.get("obj_niv_l_id")),
        _to_int(qv.get("obj_niv_r_id")),
    }
    qv_ids.discard(None)
    lane_assignment = str(obj.get("lane_assignment") or "").lower()
    lane_relevant = bool(qv_ids and obj_id is not None and obj_id in qv_ids)
    lane_relevant = lane_relevant or _contains_any(lane_assignment, ("cipv", "niv", "vru", "ego", "adj", "host"))
    heading_related = _contains_any(issue.get("rule"), ("heading", "yaw")) or _contains_any(issue.get("issue_type"), ("heading", "yaw")) or _contains_any(issue.get("feature"), ("heading", "yaw"))
    problem_signal = _issue_signal_label(issue).lower()
    rule_text = str(issue.get("rule") or "").lower()
    control_relevant_jump = (
        "od_ttc_risk" in rule_text
        or heading_related
        or any(token in problem_signal for token in ("long", "lat", "vel", "speed", "heading", "ttc"))
    )
    near_adjacent_lane = (
        long_dist is not None
        and abs_lat is not None
        and 0.0 <= long_dist <= 30.0
        and 2.0 < abs_lat <= 5.0
    )
    return {
        "ttc": ttc,
        "long_dist": long_dist,
        "lat_dist": lat_dist,
        "abs_lat": abs_lat,
        "existence_prob": existence_prob,
        "lane_assignment": lane_assignment,
        "lane_relevant": lane_relevant,
        "heading_related": heading_related,
        "obj_id": obj_id,
        "obj_class": str(obj.get("class") or obj.get("VIS_OBJ_Object_Class") or ""),
        "obj_motion_status": str(obj.get("motion_status") or obj.get("VIS_OBJ_Motion_State", {}).get("Motion_Status") or ""),
        "obj_motion_category": str(obj.get("motion_category") or obj.get("VIS_OBJ_Motion_State", {}).get("Motion_Category") or ""),
        "obj_rel_long_vel": _to_float(obj.get("rel_long_vel")),
        "obj_rel_lat_vel": _to_float(obj.get("rel_lat_vel")),
        "obj_abs_long_vel": _to_float(obj.get("abs_long_vel")),
        "obj_abs_lat_vel": _to_float(obj.get("abs_lat_vel")),
        "near_adjacent_lane": near_adjacent_lane,
        "control_relevant_jump": control_relevant_jump,
    }


def _is_stationary_or_parked(snap: dict[str, Any]) -> bool:
    motion_text = f"{snap.get('obj_motion_status', '')} {snap.get('obj_motion_category', '')}".lower()
    if any(token in motion_text for token in ("park", "parking", "parked", "stop", "stopped", "stationary", "standstill", "static")):
        return True
    abs_long = _to_float(snap.get("obj_abs_long_vel"))
    abs_lat = _to_float(snap.get("obj_abs_lat_vel"))
    if abs_long is not None and abs_lat is not None and abs(abs_long) <= 0.5 and abs(abs_lat) <= 0.3:
        return True
    return False


def _apply_adas_priority_floor(priority: Any, snap: dict[str, Any], issue: dict[str, Any]) -> int | str:
    p = _to_int(priority)
    if p is None:
        return priority
    if not (snap.get("near_adjacent_lane") and snap.get("control_relevant_jump")):
        return p
    # Near adjacent-lane dynamic jumps can be planning/control relevant.
    # Within 20 m longitudinal distance, treat it as very close and keep P2
    # unless the object is parked/stationary.
    if _is_stationary_or_parked(snap):
        return min(p, 3)
    long_dist = _to_float(snap.get("long_dist"))
    if long_dist is not None and long_dist <= 20.0:
        return min(p, 2)
    if snap.get("heading_related"):
        return min(p, 2)
    return min(p, 3)


def _has_downgrade_separation_evidence(result: dict[str, Any]) -> bool:
    text = " ".join(str(result.get(key) or "") for key in (
        "final_reasoning",
        "non_issue_reason",
        "image_observation",
        "referenced_data",
        "data_gaps",
    )).lower()
    # Parked/stationary alone should only downgrade to P3. P4/P5 downgrade
    # needs explicit non-crossable separation evidence.
    separation_tokens = (
        "road edge",
        "median",
        "barrier",
        "non-drivable",
        "중앙분리",
        "로드엣지",
        "로드 엣지",
        "장애물",
        "차단",
        "물리적 분리",
        "가로막",
        "막혀",
        "충돌 가능성 낮",
    )
    return any(token in text for token in separation_tokens)


def _has_stationary_text_evidence(result: dict[str, Any]) -> bool:
    text = " ".join(str(result.get(key) or "") for key in (
        "final_reasoning",
        "non_issue_reason",
        "image_observation",
        "referenced_data",
    )).lower()
    patterns = (
        r"정차해",
        r"정차한",
        r"정차 차량",
        r"주차",
        r"parked",
        r"stopped vehicle",
        r"stationary vehicle",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _postprocess_llm_priority(result: dict[str, Any], issue: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    snap = _build_numeric_snapshot(issue, context)
    if not (snap.get("near_adjacent_lane") and snap.get("control_relevant_jump")):
        return result
    original = _to_int(result.get("priority_1_to_5"))
    if original is None:
        return result
    if _has_downgrade_separation_evidence(result):
        return result
    stationary_or_parked = _is_stationary_or_parked(snap) or _has_stationary_text_evidence(result)
    long_dist = _to_float(snap.get("long_dist"))
    floor_priority = 3 if stationary_or_parked else 2 if long_dist is not None and long_dist <= 20.0 else 3
    if original <= floor_priority:
        return result
    result["priority_1_to_5"] = floor_priority
    if result.get("final_decision") == "이슈 아님":
        result["final_decision"] = "우선순위 낮은 이슈"
        result["non_issue_reason"] = ""
    reason = str(result.get("final_reasoning") or "").strip()
    if stationary_or_parked:
        floor_note = (
            "정차/주차 가능성은 downgrade 근거이지만, 근거리 인접차선 종방향/속도/heading 점프는 "
            "TTC와 target selection에 영향을 줄 수 있어 최종 우선순위를 P3로 보정했습니다."
        )
    else:
        floor_note = (
            "종거리 20m 이내 근거리 인접차선 동적 신호 점프는 cut-in 및 ACC/AEB/FCW target selection에 영향을 줄 수 있고, "
            f"명확한 Road Edge/median/barrier 분리 근거가 없어 최종 우선순위를 P{floor_priority}로 보정했습니다."
        )
    result["final_reasoning"] = f"{reason} {floor_note}".strip()
    result["recommended_action"] = result.get("recommended_action") or "근거리 인접차선 동적 이슈 재확인"
    return result


def _routing_decision(
    issue: dict[str, Any],
    context: dict[str, Any],
    use_images: bool,
    image_status: str,
    llm_priority_max: int,
) -> dict[str, Any]:
    snap = _build_numeric_snapshot(issue, context)
    ttc = snap["ttc"]
    long_dist = snap["long_dist"]
    lat_dist = snap["lat_dist"]
    abs_lat = snap["abs_lat"]
    existence_prob = snap["existence_prob"]
    lane_relevant = snap["lane_relevant"]
    heading_related = snap["heading_related"]
    near_adjacent_lane = snap["near_adjacent_lane"]
    control_relevant_jump = snap["control_relevant_jump"]
    stationary_or_parked = _is_stationary_or_parked(snap)
    problem_signal = _issue_signal_label(issue)
    signal_detail = _primary_signal_detail(issue)
    llm_reasons: list[str] = []
    needs_llm = True
    final_decision = "판단 보류"
    priority = ""
    issue_priority = _issue_priority_score(issue)

    if heading_related:
        llm_reasons.append("헤딩 계열은 ROI/연속성과 BEV상 주행 가능 영역 확인이 필요합니다")
    if issue_priority is not None and issue_priority <= llm_priority_max:
        llm_reasons.append(f"룰 우선순위가 높아(P{issue_priority}) LLM이 카메라 이미지와 BEV를 함께 확인해야 합니다")

    if ttc is None or long_dist is None or lat_dist is None:
        llm_reasons.append("TTC 또는 거리 핵심 수치가 부족해 JSON/이미지 종합 판단이 필요합니다")
    if existence_prob is not None and existence_prob < 0.55:
        llm_reasons.append(f"인지 신뢰도가 낮아({_fmt_num(existence_prob, 2)}) 실제 객체 여부 확인이 필요합니다")
    if abs_lat is not None and 2.0 <= abs_lat < 5.0:
        llm_reasons.append(f"횡거리 {_fmt_num(abs_lat, 2)}m 경계 구간이라 ego path 영향 판단이 필요합니다")
    if near_adjacent_lane and control_relevant_jump:
        if stationary_or_parked:
            llm_reasons.append("근거리 인접차선 객체이나 정차/주차 가능성이 있어 제어 영향 downgrade 여부 확인이 필요합니다")
        else:
            llm_reasons.append("근거리 인접차선 동적 이슈로 cut-in, ACC/AEB/FCW target selection 영향 가능성 확인이 필요합니다")
    if ttc is not None and 1.0 < ttc < 2.5:
        llm_reasons.append(f"TTC {_fmt_num(ttc, 2)}s 경계 구간이라 위험도 보강 판단이 필요합니다")
    if use_images and image_status in {"from_screenshot_path", "from_synced_folder_frame_rule", "from_synced_folder_rowtag"} and abs_lat is not None and abs_lat < 6.0:
        llm_reasons.append("좌측 원본 이미지와 우측 BEV에서 ego path, road edge, non-drivable 영역 확인이 필요합니다")

    clear_issue = (
        not heading_related
        and ttc is not None
        and long_dist is not None
        and lat_dist is not None
        and lane_relevant
        and ttc <= 1.0
        and long_dist <= 25
        and abs_lat is not None
        and abs_lat <= 1.5
        and (existence_prob is None or existence_prob >= 0.6)
    )
    clear_not_issue = (
        not heading_related
        and ttc is not None
        and long_dist is not None
        and lat_dist is not None
        and abs_lat is not None
        and abs_lat >= 5.0
        and (ttc >= 2.5)
        and long_dist >= 20
        and not lane_relevant
        and (existence_prob is None or existence_prob >= 0.5)
    )

    if clear_issue:
        needs_llm = False
        final_decision = "실제 이슈"
        priority = 1 if ttc is not None and ttc <= 0.7 else 2
        llm_reasons = []
    elif clear_not_issue:
        needs_llm = False
        final_decision = "이슈 아님"
        priority = 5
        llm_reasons = []
    else:
        if issue_priority is not None and issue_priority > llm_priority_max and not heading_related and not (near_adjacent_lane and control_relevant_jump):
            needs_llm = False
            final_decision = "우선순위 낮은 이슈"
            priority = max(3, min(5, issue_priority))
            llm_reasons = []
        elif not llm_reasons:
            llm_reasons.append("경계값 또는 ROI 관련성이 불명확해 LLM 검토가 필요합니다")

    if not priority and issue_priority is not None:
        priority = max(1, min(5, issue_priority))
    priority = _apply_adas_priority_floor(priority, snap, issue)
    pre_review_reason = _adas_priority_reason(
        priority,
        issue.get("role"),
        long_dist,
        abs_lat,
        ttc,
        signal_detail,
        lane_relevant,
    )
    llm_need_reason = _llm_need_reason_text(llm_reasons, needs_llm)
    routing_reason = llm_need_reason or pre_review_reason
    decision_source = "사전 판정" if not needs_llm else "LLM 검토 대상"

    return {
        "needs_llm": needs_llm,
        "routing_reason": routing_reason,
        "pre_review_reason": pre_review_reason,
        "llm_need_reason": llm_need_reason,
        "decision_source": decision_source,
        "final_decision": final_decision,
        "priority_1_to_5": priority,
        "confidence_0_to_1": 0.9 if not needs_llm else 0.0,
        "issue_summary": signal_detail["evidence_sentence"],
        "rule_trigger_basis": _rule_trigger_basis(issue, context),
        "referenced_data": f"{signal_detail['primary_signal']}, {signal_detail['signal_value']}, {signal_detail['delta_vs_lidar'] or 'LiDAR 오차 해당 없음'}, TTC={_fmt_num(ttc)}s, 종거리={_fmt_num(long_dist)}m, 횡거리={_fmt_num(abs_lat)}m, 차선할당={snap['lane_assignment'] or '-'}",
        "image_observation": "이미지 미참조" if image_status == "not_requested" else "이미지 참고 가능",
        "final_reasoning": pre_review_reason,
        "non_issue_reason": "" if final_decision != "이슈 아님" else pre_review_reason,
        "recommended_action": "LLM 검토" if needs_llm else ("수동 재확인" if final_decision == "실제 이슈" else "추가 조치 없음"),
        "data_gaps": "" if not needs_llm else "경계값 또는 ROI 관련성이 불명확함",
    }


def _rule_trigger_basis(issue: dict[str, Any], context: dict[str, Any]) -> str:
    obj = context.get("target_object_curr") or {}
    parts = [
        f"rule={issue.get('rule')}",
        f"issue_type={issue.get('issue_type')}",
        f"feature={issue.get('feature')}",
        f"frame={issue.get('frame')}",
        f"object_id={issue.get('object_id')}",
    ]
    for key in ("ttc", "long_dist", "lat_dist", "current_value", "previous_value"):
        if issue.get(key) is not None:
            parts.append(f"{key}={issue.get(key)}")
    for key in ("ttc_from_inv_ttc", "inv_ttc", "rel_long_vel", "existence_prob", "lane_assignment"):
        if obj.get(key) is not None:
            parts.append(f"qv.{key}={obj.get(key)}")
    return ", ".join(parts)


def _context_for_llm(
    row_index: int,
    issue: dict[str, Any],
    context: dict[str, Any],
    exported_issue_context: dict[str, Any] | None,
    image_path: Path | None,
    image_status: str,
    image_note: str,
    routing: dict[str, Any],
) -> dict[str, Any]:
    return {
        "row_index": row_index,
        "task": "QV 규칙 검출 이슈에 대한 최종 QA 판정.",
        "decision_labels": ["실제 이슈", "우선순위 낮은 이슈", "이슈 아님", "판단 보류"],
        "priority_scale": "1=가장 높음, 5=가장 낮음",
        "issue_from_excel": issue,
        "rule_trigger_basis": _rule_trigger_basis(issue, context),
        "qv_parsed_context": context,
        "qv_exported_issue_context": exported_issue_context or {},
        "routing_summary": {
            "needs_llm": routing.get("needs_llm"),
            "decision_source": routing.get("decision_source"),
            "routing_reason": routing.get("routing_reason"),
        },
        "image_evidence": {
            "enabled": image_path is not None,
            "path": str(image_path) if image_path else "",
            "status": image_status,
            "note": image_note,
            "layout_hint": (
                "The left side is the original camera/ICS image with JSON and optional LiDAR drawings. "
                "The right side is BEV generated from logs. Use the left image for road scene, visibility, occlusion, and box quality. "
                "Use BEV for ego-path relevance, road edge, median separation, adjacent lane, and non-drivable area. "
                "Issue target is highlighted in yellow when available: yellow box in ICS, yellow circle in BEV. "
                "Use qv_image_legend_fvc.md to interpret OD/LD/TS/TL/SOD/FSD/LiDAR overlays, labels, and colors."
            ),
        },
        "review_instructions": [
            "원래 룰이 어떤 데이터 때문에 이슈로 잡혔는지 설명하세요.",
            "QV 이미지 레전드(qv_image_legend_fvc.md)를 참고해 OD/LD/TS/TL/SOD/FSD/LiDAR 레이어와 색상/라벨 의미를 해석하세요.",
            "LiDAR Distance는 Long Error와 Lat Error 중 실제 문제 신호를 하나로 특정하고, JSON 값과 LiDAR 값 및 오차를 반드시 쓰세요.",
            "LiDAR FN은 Signal Delta를 만들지 말고, 어떤 LiDAR 객체가 어떤 perception stream에서 미검출 후보인지 설명하세요.",
            "최종 판정에 참고한 신호와 값을 명시하세요.",
            "ADAS/AD 시스템의 카메라 인식 QA 엔지니어 관점에서 자율주행 제어 로직에 실제 영향을 줄 수 있는지 판단하세요.",
            "좌측 원본 이미지에서는 현재 도로 상황, 객체 가시성, occlusion, 박스 품질을 확인하세요.",
            "우측 BEV에서는 객체가 ego path, road edge, median, adjacent lane, non-drivable area 중 어디에 있는지 확인하세요.",
            "실제 이슈, 우선순위 낮은 이슈, 이슈 아님, 판단 보류 중 하나로 판정하세요.",
            "이슈 아님이면 왜 아닌지 명확하게 설명하세요.",
            "이미지가 있으면 가시성, 가림, 횡방향 위치, ego 영향 판단에 사용하세요.",
            "ICS는 가시성/가림/박스 품질, BEV는 ego path/road edge/median/adjacent lane/non-drivable area 판단에 사용하세요.",
            "OD/TTC는 TTC만 보지 말고 ego path relevance, lateral offset, road edge/median separation, adjacent lane, edge-of-FOV, non-drivable area를 함께 보세요.",
            "객체가 host drivable corridor 밖이면 ADAS/AD 영향이 명확하지 않은 한 우선순위를 낮추거나 이슈 아님으로 보세요.",
            "주어진 컨텍스트 밖의 정보를 만들어내지 마세요.",
            "모든 서술형 텍스트는 한국어만 사용하세요. 영어는 표준 약어(TTC, BEV, ICS 등)만 최소한으로 허용합니다.",
        ],
    }


def _load_domain_guidance() -> str:
    guidance_path = Path(__file__).resolve().parents[1] / "references" / "domain_judgment_guidance.md"
    try:
        return guidance_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _load_image_legend() -> str:
    legend_path = Path(__file__).resolve().parents[1] / "references" / "qv_image_legend_fvc.md"
    try:
        return legend_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _rule_key_from_context(review_context: dict[str, Any]) -> str:
    issue = review_context.get("issue_from_excel") or {}
    rule = str(issue.get("rule") or "").upper()
    issue_type = str(issue.get("issue_type") or "").lower()
    feature = str(issue.get("feature") or "").lower()
    joined = f"{rule} {issue_type} {feature}"
    if "OD_TTC_RISK" in rule or "ttc" in joined:
        return "od_ttc"
    if "HEADING" in joined or "yaw" in joined:
        return "od_heading"
    if "LIDAR" in rule and "FN" in joined:
        return "lidar_fn"
    if "LIDAR" in rule and "FP" in joined:
        return "lidar_fp"
    if "LIDAR" in rule and ("DIST" in joined or "distance" in joined):
        return "lidar_distance"
    if "LIDAR" in rule and ("SPEED" in joined or "VEL" in joined or "velocity" in joined):
        return "lidar_speed"
    return "generic"


def _focused_domain_guidance(review_context: dict[str, Any]) -> str:
    rule_key = _rule_key_from_context(review_context)
    common = """
# Focused QV Final QA Guidance

Use this compact guidance for this row only. Judge as an ADAS/AD camera perception QA engineer. Priority scale: P1 highest, P5 lowest.

## Common
- Judge whether the rule-detected issue can affect ADAS/AD control logic, not only whether the rule condition fired.
- Use a SOTIF perspective: judge whether intended-function/perception limitations can create safety risk even without component failure.
- Explain the ADAS/AD impact path when applicable: FCW/AEB/ACC target selection, TTC/risk estimation, cut-in gating, lane relevance, trajectory prediction, path planning, or driver/vehicle response.
- Explain severity in the final reasoning: immediate control/collision risk, important SOTIF-relevant perception weakness, potential reportable perception instability, customer-visible cleanup concern, or no meaningful control/SOTIF relevance.
- Report plausible perception risks, not only confirmed defects. P1-P3 are reportable issues, P4 is a customer-visible cleanup concern that is not a current issue, and P5 is not a problem.
- P1 means severe near-field CIPV, near-field VRU, or adjacent-lane control-malfunction risk. Do not make long-range CIPV P1 by role alone.
- P2 means important NIV/adjacent-lane/near-field issue with plausible FCW/AEB/ACC, cut-in, TTC, target-selection, or trajectory-prediction impact.
- P3 means potential issue worth reporting even when immediate control impact is uncertain.
- Use parsed JSON values as the stable numeric source and screenshots as visual evidence.
- Downgrade objects clearly outside the ego drivable corridor, beyond road edge/median, or in non-drivable areas unless they can still affect control.
- Do not over-downgrade near-field objects with plausible ego-path, cut-in, FCW/AEB/ACC target-selection, or VRU safety relevance.
- For near-field adjacent-lane distance, velocity, or heading jumps, use P2 when longitudinal distance is within 20 m because that is very close for ADAS control.
- Prioritize close adjacent-position issues conservatively; lateral distance or lateral velocity jumps can be more control-relevant than a pure longitudinal distance jump.
- If the same target is parked/stationary but still adjacent and close, downgrade only to P3 unless there is clear non-crossable Road Edge/median/barrier separation.
- Only clear Road Edge line, median, barrier, or other non-crossable obstacle between ego and target can justify P4/P5 or non-issue for close adjacent-lane dynamic jumps.
- If the object heading/orientation points toward the host lane or ego path, raise priority because cut-in prediction and trajectory gating can become unstable.
- Consider road and traffic context from JSON and image. Highway/high-speed-road or visually high-speed situations should raise the severity of close object instability; parking lots, stopped traffic, low-speed urban congestion, or clearly slow maneuvering can lower severity when ego-control impact is limited.
- Do not infer host speed from image alone when JSON/CAN speed is unavailable. Use image scene type as supporting context and explain uncertainty.
- FSD/free-space is only supporting context. Do not use FSD termination alone as a downgrade reason because FSD can naturally stop at vehicles, pedestrians, or obstacles.
- Write concise Korean explanations with concrete values when available.
""".strip()
    by_rule = {
        "od_ttc": """
## OD TTC Risk
- Treat TTC as a risk indicator, not final severity by itself.
- Combine TTC with longitudinal distance, lateral offset, role/lane assignment, road edge/median separation, object type, and kinematics.
- For OD TTC Risk, the meaningful comparison is usually previous-frame vs current-frame signal jump, not LiDAR delta.
- Near-field adjacent-lane bus/truck/large vehicle jumps can still be P2-P3 because planning/control may interpret them as cut-in or collision-risk candidates.
- Keep near-field adjacent-lane large objects within roughly 30 m longitudinal distance and 2.0-3.5 m lateral offset at least medium priority.
- In city/intersection scenes, a close adjacent-lane bus with about a 5 m lateral-distance jump is normally P2; consider P1 only if it appears to enter ego path, occurs in a higher-risk driving context, or can directly trigger control malfunction.
- If longitudinal distance is within 20 m, prefer P2 unless clear Road Edge/median/barrier separation exists.
- For adjacent-lane oncoming vehicles with longitudinal distance jumps, use at least P2 when close; if the scene is a dark underpass or bridge shadow, describe it as a condition-specific perception weakness and usually keep P2 rather than P1.
- If the same adjacent-lane case has lateral distance or lateral velocity jumping instead of only longitudinal distance, consider P1 when ego-path relevance or ADAS control can be disturbed.
- If the object is parked/stationary, prefer P3 rather than P5 because a longitudinal jump can still affect TTC or target selection.
- For adjacent-lane distance/velocity jumps, check if heading/orientation points toward ego lane. If yes, raise priority; if parked/stationary, lower priority carefully.
- High priority usually requires near-field distance, short TTC, and plausible ego-path overlap.
""",
        "od_heading": """
## OD Heading Change
- Judge whether the heading jump persists or returns, and whether the object is inside the relevant ROI.
- Explicitly compare previous heading, current heading, and delta when values are available.
- Do not exclude or downgrade based on FSD alone. FSD is a supporting cue only because it can stop at detected objects or pedestrians.
- Downgrade strongly only when a green Road Edge line, median, barrier, or other non-crossable separation is clearly between ego and target.
- For vehicles near ego path, a large heading jump can affect tracking continuity, cut-in estimation, and trajectory prediction.
- Adjacent-lane heading flips near the ego vehicle should normally be at least P3, and P2 if the object appears oriented toward the host lane or could enter ego path.
- A close cyclist/VRU heading jump may remain P3 when it has meaningful lateral offset and is not directly in ego path; raise to P1-P2 when it is in front of ego or can enter ego path.
""",
        "lidar_fn": """
## LiDAR FN
- A LiDAR FN means a LiDAR object has insufficient matched camera perception evidence.
- Do not use Signal Delta vs LiDAR for FN; explain missed-object evidence instead.
- Consider object type, distance, lateral offset, ego-path relevance, occlusion by a nearer object, road edge, and range.
- A far object behind a nearer occluding object can be low priority or non-issue; a close ego-path object should not be downgraded.
""",
        "lidar_fp": """
## LiDAR FP
- A LiDAR FP means a camera object lacks a valid LiDAR match.
- If the camera object is stable for multiple frames and confidence is high, it may be a valid camera object rather than a true FP.
- Downgrade objects outside road edge/non-drivable areas; keep ego-path or near-field VRU/vehicle cases higher.
""",
        "lidar_distance": """
## LiDAR Distance Mismatch
- Explicitly name Long Error or Lat Error and include JSON value, LiDAR value, and error magnitude.
- Use BEV to judge whether the mismatch matters for ego-path control.
- Longitudinal errors near ego path can affect ACC/AEB/FCW timing; lateral errors can affect lane/cut-in relevance.
""",
        "lidar_speed": """
## LiDAR Velocity Mismatch
- Explicitly name longitudinal or lateral velocity mismatch and include values when available.
- Judge whether the velocity error can affect TTC, cut-in prediction, target selection, or control stability.
""",
        "generic": """
## Generic
- Explain which rule value triggered the issue and which evidence changes final severity.
- Use ego-path relevance, lateral offset, distance, object type, visibility, and persistence to set priority.
""",
    }
    return common + "\n\n" + by_rule.get(rule_key, by_rule["generic"]).strip()


def _focused_image_legend(review_context: dict[str, Any]) -> str:
    rule_key = _rule_key_from_context(review_context)
    common = """
# Focused QV FVC Image Legend

## Layout And Target
- Left side is original camera/ICS; right side is BEV.
- Yellow rectangle in ICS and yellow circle in BEV indicate the issue target when available.
- First match the target by row id/object id/class text and yellow highlight. If the highlight looks wrong, report target-sync risk and rely more on parsed JSON.

## BEV Reference
- The blue rectangle near the bottom center is the host/ego vehicle.
- The BEV grid is 5 meters per cell.
- Use the blue ego box as the reference for ego path, longitudinal distance, lateral offset, and control relevance.
- For OD objects, JSON `long_dist`/`lat_dist` correspond to the white rear-center point on the BEV object box, not the visual box center.
- For issue targets, the yellow BEV circle is usually on or near this same rear-center reference point.

## Numeric Sources
- Use parsed JSON as the primary source for exact distance, velocity, TTC, heading, object id, class, lane assignment, existence probability, and signal deltas.
- Use parsed JSON `heading` together with BEV rotated-box orientation to judge object direction, cut-in/crossing/oncoming relevance, and movement toward or away from the host lane.

## Visual Sources
- Use ICS for visibility, occlusion, edge-of-FOV, object-box quality, and road-scene context.
- Use BEV for ego-path relevance, lateral/longitudinal position, adjacent-lane relevance, Road Edge/median/barrier separation, and non-drivable-area judgment.
- Lane and Road Edge detections appear in both ICS and BEV. Road Edge is always a green line. Normal lanes use the detected lane color, so a detected white lane is drawn as a white line.
- Distinguish the green Road Edge line from the semi-transparent green FSD/free-space area. Road Edge is a boundary cue; FSD is only supporting context and can stop at objects or pedestrians.
- Use road-scene context from ICS/BEV and JSON road flags when available: highway/high-speed road, arterial/city road, intersection, underpass/bridge shadow, parking lot, stopped traffic, congestion, or low-speed maneuvering.
- Do not estimate exact host speed from the image alone. If JSON/CAN speed is unavailable, describe the scene as visual context only.

## Judgment Rule
- Final judgment must combine JSON object values with screenshot context to decide real issue / low-priority issue / non-issue and priority.
- Downgrade strongly only when Road Edge, median, barrier, curb, or another non-crossable separation clearly removes ego-control relevance.
- Raise priority when the same close-object instability occurs on a highway/high-speed-road or visually high-speed scene. Lower priority when the scene is a parking lot, traffic jam, or low-speed maneuvering context and the object is not control-critical.
""".strip()
    sections = {
        "od_ttc": """
## OD/TTC Visual Cues
- OD labels usually look like `[id] CLASS_ABBR`; vehicles are polygons in BEV and pedestrians are circles.
- CIPV/NIV and TTC text may be drawn near the center; CIPV/NIV can affect control relevance.
- Green Road Edge lines are strong separation cues when clearly between ego and target.
- FSD/free-space is also green/semi-transparent, but it is only supporting context because it can be blocked by objects or pedestrians.
- For adjacent-lane large vehicles, inspect BEV lateral offset and possible cut-in relevance instead of dismissing by lane alone.
""",
        "od_heading": """
## OD Heading Visual Cues
- OD boxes include id/class labels and may include heading arrows.
- Use BEV object orientation and lane/Road Edge context to decide whether heading jump matters.
- Use FSD only as supporting context; do not downgrade based on FSD alone.
""",
        "lidar_fn": """
## LiDAR FN Visual Cues
- LiDAR objects may be drawn as 2D boxes in ICS and rotated boxes/circles in BEV.
- Check whether the target LiDAR object is occluded by a nearer LiDAR object or separated by road edge/non-drivable area.
""",
        "lidar_fp": """
## LiDAR FP Visual Cues
- Camera OD object labels/boxes should be checked against LiDAR overlay presence.
- Stable visible camera objects without LiDAR match can be valid perception, especially if not safety-critical.
""",
        "lidar_distance": """
## LiDAR Distance Visual Cues
- Compare camera OD position and LiDAR overlay in ICS/BEV.
- Use BEV to judge whether longitudinal/lateral mismatch affects ego path or adjacent-lane interpretation.
""",
        "lidar_speed": """
## LiDAR Velocity Visual Cues
- Speed mismatch may not be directly visible; use parsed JSON values as primary evidence.
- Use BEV/ICS only to judge whether the target object is control-relevant.
""",
        "generic": """
## Generic Visual Cues
- Identify the highlighted target and use labels/IDs plus parsed JSON values.
""",
    }
    return common + "\n\n" + sections.get(rule_key, sections["generic"]).strip()


def _expected_result_schema() -> dict[str, Any]:
    return {
        "final_decision": "실제 이슈 | 우선순위 낮은 이슈 | 이슈 아님 | 판단 보류",
        "priority_1_to_5": 1,
        "confidence_0_to_1": 0.0,
        "issue_summary": "예: 종방향 거리 오차가 4.8m 발생해 ACC/AEB target selection에 영향 가능",
        "rule_trigger_basis": "예: Long Error=4.8m, JSON long=22.1m, LiDAR long=26.9m",
        "referenced_data": "예: ego path 관련성, 종거리, 횡거리, TTC, heading, road context",
        "image_observation": "예: BEV에서 ego path와 겹치며 Road Edge 분리 근거 없음",
        "final_reasoning": "예: SOTIF 관점에서 인식 거리 불안정이 TTC/risk estimation과 ACC/AEB target selection에 영향을 줄 수 있어 P2로 판단",
        "non_issue_reason": "예: Road Edge/median으로 ego path와 명확히 분리되어 ADAS/AD 제어 영향 및 SOTIF 관련성이 낮음",
        "recommended_action": "예: 즉시 재검토",
        "data_gaps": "예: 이미지나 차선 정보가 불명확함",
    }


def _signal_columns(issue: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    obj = context.get("target_object_curr") or {}
    return {
        "Long Distance [m]": issue.get("long_dist") if issue.get("long_dist") is not None else obj.get("long_dist"),
        "Lateral Distance [m]": issue.get("lat_dist") if issue.get("lat_dist") is not None else obj.get("lat_dist"),
        "TTC [s]": issue.get("ttc") if issue.get("ttc") is not None else obj.get("ttc_from_inv_ttc"),
        "Absolute Longitudinal Velocity [m/s]": obj.get("abs_long_vel"),
        "Absolute Lateral Velocity [m/s]": obj.get("abs_lat_vel"),
        "Existence Probability": obj.get("existence_prob"),
        "Lane Position": obj.get("lane_assignment"),
        "Issue Signal": _issue_signal_label(issue),
    }


def _infer_problem_signal(issue: dict[str, Any]) -> str:
    rule = str(issue.get("rule") or "").upper()
    issue_type = str(issue.get("issue_type") or "").lower()
    if "TTC" in rule or "ttc" in issue_type:
        return "TTC / inv_ttc"
    if "DIST" in rule or "distance" in issue_type:
        return "long_dist / lat_dist"
    if "VEL" in rule or "velocity" in issue_type:
        return "rel_long_vel / rel_lat_vel"
    if "ID" in rule:
        return "object_id / track continuity"
    return str(issue.get("problem_signal") or "")


def _parse_result_file(result_path: Path) -> dict[str, Any]:
    data = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("result JSON is not an object")
    decision = str(data.get("final_decision", "")).strip()
    if decision not in VALID_DECISIONS:
        raise ValueError(f"invalid final_decision: {decision}")
    try:
        priority = int(data.get("priority_1_to_5"))
    except Exception as exc:
        raise ValueError("priority_1_to_5 is not an integer") from exc
    if priority < 1 or priority > 5:
        raise ValueError(f"invalid priority_1_to_5: {priority}")
    data["priority_1_to_5"] = priority
    return data


def _extract_tokens_used(text: str) -> int:
    matches = re.findall(r"tokens used\s+([\d,]+)", text, flags=re.IGNORECASE)
    if not matches:
        return 0
    total = 0
    for raw in matches:
        try:
            total += int(raw.replace(",", ""))
        except Exception:
            continue
    return total


def _call_codex_file_review(
    review_context: dict[str, Any],
    model: str,
    image_path: Path | None,
    repo_root: Path,
    guidance_mode: str,
) -> tuple[dict[str, Any] | None, str, int]:
    codex_bin = shutil.which("codex.cmd") or shutil.which("codex") or "codex"
    with tempfile.TemporaryDirectory(prefix="qv_llm_review_") as td:
        td_path = Path(td)
        context_path = td_path / "issue_context.json"
        result_path = td_path / "qa_result.json"
        guidance_path = td_path / "domain_judgment_guidance.md"
        image_legend_path = td_path / "qv_image_legend_fvc.md"
        context_path.write_text(json.dumps(review_context, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        if guidance_mode == "focused":
            guidance_text = _focused_domain_guidance(review_context)
            image_legend_text = _focused_image_legend(review_context)
        else:
            guidance_text = _load_domain_guidance()
            image_legend_text = _load_image_legend()
        guidance_path.write_text(guidance_text, encoding="utf-8")
        image_legend_path.write_text(image_legend_text, encoding="utf-8")

        prompt = f"""
You are the final QA engineer for Qualification Visualizer issue triage.

Read this context file:
{context_path}

Read this domain judgment guidance:
{guidance_path}

Read this QV FVC image legend:
{image_legend_path}

Write the final judgment JSON to this exact path:
{result_path}

The output file must be one JSON object using this schema:
{json.dumps(_expected_result_schema(), ensure_ascii=False, indent=2)}

Important:
- The JSON file is the deliverable. Do not rely on stdout.
- Use the QV parsed context and attached image when available.
- Use the QV FVC image legend to interpret OD/LD/TS/TL/SOD/FSD/LiDAR overlays, labels, colors, and yellow target highlights.
- Be specific about which values/signals caused the issue and which values affected your final judgment.
- Include ADAS/AD control-impact reasoning in final_reasoning: FCW/AEB/ACC target selection, TTC/risk estimation, cut-in gating, lane relevance, trajectory prediction, path planning, or driver/vehicle response when relevant.
- Include SOTIF perspective in final_reasoning: whether this is an intended-function/perception limitation risk even without component failure.
- Explain the severity nature behind priority: immediate control/collision risk, important SOTIF-relevant perception weakness, potential reportable perception instability, customer-visible cleanup concern, or no meaningful ADAS/AD control/SOTIF relevance.
- For LiDAR distance issues, explicitly name Long Error or Lat Error, include JSON value, LiDAR value, and error magnitude.
- For LiDAR FN issues, do not discuss Signal Delta vs LiDAR; explain the missed-object evidence and whether occlusion, road edge, ego-path relevance, or range lowers priority.
- Explain why the final priority was raised or lowered using ego path relevance, lateral offset, distance, object type, visibility, and safety impact.
- Use this reporting scale: P1 severe issue; P2 important issue; P3 potential but reportable issue; P4 not a current issue but customer-visible cleanup concern; P5 not a problem.
- Map that scale to SOTIF/control impact: P1 severe control/SOTIF risk, P2 important SOTIF-relevant control-impact risk, P3 potential reportable perception weakness, P4 cleanup/robustness concern, P5 no meaningful problem.
- For near-field adjacent-lane distance, velocity, or heading jumps, use P2 when longitudinal distance is within 20 m.
- Treat close lateral distance or lateral velocity jumps more severely than pure longitudinal jumps when they can affect lane relevance, cut-in prediction, or target selection.
- Parked/stationary close adjacent-lane targets should usually be P3, not P5, because distance jumps can still affect TTC and target selection.
- Do not reduce close adjacent-lane dynamic jumps to P4/P5 unless a green Road Edge line, median, barrier, or other non-crossable obstacle clearly separates ego and target.
- If the target orientation/heading suggests movement toward the host lane, raise priority because cut-in prediction, FCW/AEB/ACC target selection, or trajectory gating may be affected.
- If an oncoming object is physically blocked from ego by a median/barrier/Road Edge/parked vehicles, downgrade and explain the separation evidence.
- FSD/free-space is supporting context only. Do not treat FSD ending before an object as proof that the object is irrelevant.
- Act as an ADAS/AD camera perception QA engineer. Judge whether the issue can affect autonomous driving control logic.
- If an image is attached, remember: left side is original camera/ICS, right side is BEV. Use camera view for road scene and visibility; use BEV for ego-path, road-edge, median, adjacent-lane, and non-drivable-area relevance.
- If the yellow highlight appears mis-synced with the row target, mention capture/target-sync risk and rely more on parsed JSON and row values.
- Use ADAS/AD, vision perception, and QA test terminology such as TTC risk, lateral offset, ego path relevance, near-field object, perception stability, edge-of-FOV, occlusion, tracking continuity, object kinematics, false positive, and safety impact.
- Write every text field in Korean only. Avoid mixing English and Korean except for standard acronyms such as TTC, BEV, and ICS.
- Keep every text field concise but concrete: one or two short sentences with numbers when available.
- Do not return {{"status":"ok"}}, {{"ok":true}}, or an empty object.
"""
        cmd = [
            codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--ignore-rules",
            "--cd",
            str(td_path),
            "--add-dir",
            str(td_path),
            "--add-dir",
            str(repo_root),
            "--color",
            "never",
        ]
        if model:
            cmd.extend(["--model", model])
        if image_path is not None and image_path.exists():
            cmd.extend(["--image", str(image_path)])
        cmd.append("-")

        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        token_text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        tokens_used = _extract_tokens_used(token_text)
        if proc.returncode != 0:
            tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-1200:]
            return None, f"codex_exec_failed: {tail}", tokens_used
        if not result_path.exists():
            tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-1200:]
            return None, f"llm_result_file_missing: {tail}", tokens_used
        try:
            return _parse_result_file(result_path), "", tokens_used
        except Exception as exc:
            raw = result_path.read_text(encoding="utf-8", errors="replace")[:1200]
            return None, f"llm_result_schema_invalid: {exc}; raw={raw}", tokens_used


def _failure_result(error: str, review_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "final_decision": "LLM 판정 실패",
        "priority_1_to_5": "",
        "confidence_0_to_1": "",
        "issue_summary": "LLM이 최종 QA 판정 파일을 생성하지 못했습니다.",
        "rule_trigger_basis": review_context.get("rule_trigger_basis", ""),
        "referenced_data": "QV 파서 컨텍스트는 생성되었으나 LLM 결과가 유효하지 않습니다.",
        "image_observation": "",
        "final_reasoning": "LLM 판정 실패입니다. 이 행은 사람이 직접 검토해야 합니다.",
        "non_issue_reason": "",
        "recommended_action": "llm_error와 qv_context_json 컬럼을 확인한 뒤 재실행 또는 수동 검토하세요.",
        "data_gaps": "",
        "llm_error": error,
        "decision_source": "LLM 실패",
        "routing_reason": review_context.get("routing_summary", {}).get("routing_reason", ""),
    }


def _write_excel(output_path: Path, review_df: pd.DataFrame, tech_df: pd.DataFrame) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        review_df.to_excel(writer, sheet_name="최종검토", index=False)
        review_df[review_df["판정결과"] == "실제 이슈"].to_excel(writer, sheet_name="실제이슈", index=False)
        review_df[review_df["판정결과"] == "우선순위 낮은 이슈"].to_excel(writer, sheet_name="저우선순위", index=False)
        review_df[review_df["판정결과"] == "이슈 아님"].to_excel(writer, sheet_name="이슈아님", index=False)
        review_df[review_df["판정결과"] == "LLM 판정 실패"].to_excel(writer, sheet_name="판정실패", index=False)
        tech_df.to_excel(writer, sheet_name="기술컨텍스트", index=False)

        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                header = str(col[0].value or "")
                width = 18
                if header in {"최종판단", "참조데이터", "룰기반근거", "권고조치", "LLM오류", "qv_context_json"}:
                    width = 55
                elif header in {"이슈요약", "이미지판단", "Routing Reason"}:
                    width = 38
                elif header in {
                    "Long Distance [m]",
                    "Lateral Distance [m]",
                    "TTC [s]",
                    "Absolute Longitudinal Velocity [m/s]",
                    "Absolute Lateral Velocity [m/s]",
                    "Existence Probability",
                    "Lane Position",
                    "Issue Signal",
                }:
                    width = 20
                ws.column_dimensions[col[0].column_letter].width = width
                for cell in col:
                    alignment = copy(cell.alignment)
                    alignment.wrap_text = True
                    alignment.vertical = "top"
                    cell.alignment = alignment


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Final LLM QA review for QV issue Excel")
    p.add_argument("--input", required=True, help="Input Excel path with an 'issues' sheet")
    p.add_argument("--output", default=None, help="Output Excel path")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Codex model override. Default: {DEFAULT_MODEL}")
    p.add_argument(
        "--mode",
        choices=sorted(VALID_MODES),
        default=DEFAULT_MODE,
        help="Review mode: uncertain-only sends only ambiguous rows to Codex; all sends every row.",
    )
    p.add_argument("--max-rows", type=int, default=None, help="Optional row cap for testing")
    p.add_argument("--use-images", action="store_true", help="Attach synced issue capture images to Codex")
    p.add_argument(
        "--guidance-mode",
        choices=sorted(VALID_GUIDANCE_MODES),
        default="focused",
        help="LLM guidance size: focused sends rule-specific compact guidance; full sends the complete guidance files.",
    )
    p.add_argument(
        "--llm-priority-max",
        type=int,
        default=DEFAULT_LLM_PRIORITY_MAX,
        help="In uncertain-only mode, prioritize LLM review for rows with issue priority <= this value (default: 2).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    start_time = time.time()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input Excel not found: {input_path}")
        return 2

    repo_root = _find_repo_root(Path.cwd()) or _find_repo_root(input_path.parent)
    if repo_root is None:
        print("[ERROR] QV repo root not found. Run from Qualification_Visualizer or provide an input inside the repo.")
        return 2

    issues_df = pd.read_excel(input_path, sheet_name="issues")
    if args.max_rows is not None and args.max_rows >= 0:
        issues_df = issues_df.head(args.max_rows).copy()

    review_rows: list[dict[str, Any]] = []
    tech_rows: list[dict[str, Any]] = []
    total_tokens_used = 0
    llm_calls = 0

    for idx, row in issues_df.iterrows():
        issue = _issue_from_row(row)
        context = _build_context(repo_root, row.get("log_path"), row.get("frame"), row.get("object_id"))
        exported_issue_context = _load_exported_issue_context(row, input_path)
        if args.use_images:
            image_path, image_status, image_note = _resolve_image_path(row, input_path)
        else:
            image_path, image_status, image_note = None, "not_requested", ""

        routing = _routing_decision(issue, context, args.use_images, image_status, args.llm_priority_max)
        signals = _signal_columns(issue, context)
        signal_detail = _primary_signal_detail(issue)

        if args.mode == "uncertain-only" and not routing["needs_llm"]:
            llm_result = routing
            llm_error = ""
            tokens_used = 0
        else:
            review_context = _context_for_llm(
                int(idx),
                issue,
                context,
                exported_issue_context,
                image_path,
                image_status,
                image_note,
                routing,
            )
            llm_result, llm_error, tokens_used = _call_codex_file_review(
                review_context,
                args.model,
                image_path,
                repo_root,
                args.guidance_mode,
            )
            llm_calls += 1
            total_tokens_used += tokens_used
            if llm_result is None:
                llm_result = _failure_result(llm_error, review_context)
            else:
                llm_result["llm_error"] = ""
                llm_result["decision_source"] = "LLM 판정"
                llm_result["routing_reason"] = routing.get("routing_reason", "")
                llm_result = _postprocess_llm_priority(llm_result, issue, context)

        review_rows.append(
            {
                "행번호": int(idx) + 1,
                "데이터셋": issue.get("dataset"),
                "프레임": issue.get("frame"),
                "기능": issue.get("feature"),
                "Issue Rule": issue.get("rule"),
                "Rule Priority(1~5)": issue.get("priority"),
                "Role": issue.get("role"),
                "이슈유형": issue.get("issue_type"),
                "객체ID": issue.get("object_id"),
                "원본현재값": issue.get("current_value"),
                "원본이전값": issue.get("previous_value"),
                "원본기대값": issue.get("expected_value"),
                "Lidar Long [m]": issue.get("lidar_long"),
                "Lidar Lat [m]": issue.get("lidar_lat"),
                **signals,
                "Primary Signal": signal_detail.get("primary_signal"),
                "Issue Signal Value": signal_detail.get("signal_value"),
                "Delta vs Lidar": signal_detail.get("delta_vs_lidar"),
                "신호오차요약": _signal_delta_summary(issue),
                "Decision Mode": llm_result.get("decision_source") or routing.get("decision_source"),
                "판정결과": llm_result.get("final_decision"),
                "우선순위(1~5)": llm_result.get("priority_1_to_5"),
                "신뢰도(0~1)": llm_result.get("confidence_0_to_1"),
                "사전판단이유": routing.get("pre_review_reason") or routing.get("routing_reason"),
                "LLM필요사유": routing.get("llm_need_reason") if routing.get("needs_llm") else "",
                "LLM결과요약": llm_result.get("final_reasoning"),
                "이슈요약": llm_result.get("issue_summary"),
                "룰기반근거": llm_result.get("rule_trigger_basis"),
                "참조데이터": llm_result.get("referenced_data"),
                "이미지판단": llm_result.get("image_observation"),
                "최종판단": llm_result.get("final_reasoning"),
                "비이슈사유": llm_result.get("non_issue_reason"),
                "권고조치": llm_result.get("recommended_action"),
                "Routing Reason": routing.get("routing_reason"),
                "LLM오류": llm_result.get("llm_error", ""),
            }
        )
        tech_rows.append(
            {
                "행번호": int(idx) + 1,
                "Decision Mode": llm_result.get("decision_source") or routing.get("decision_source"),
                "룰기반근거": llm_result.get("rule_trigger_basis"),
                "Routing Reason": routing.get("routing_reason"),
                "데이터부족": llm_result.get("data_gaps"),
                "이미지경로": str(image_path) if image_path else "",
                "이미지상태": image_status,
                "JSON상태": ((context.get("json_files") or {}).get("current") or {}).get("status"),
                "JSON경로": ((context.get("json_files") or {}).get("current") or {}).get("used_path"),
                "qv_context_json": json.dumps(
                    (
                        review_context
                        if args.mode != "uncertain-only" or routing["needs_llm"]
                        else {
                            "row_index": int(idx),
                            "task": "QV 사전 판정 컨텍스트",
                            "issue_from_excel": issue,
                            "qv_parsed_context": context,
                            "qv_exported_issue_context": exported_issue_context or {},
                            "image_evidence": {
                                "enabled": image_path is not None,
                                "path": str(image_path) if image_path else "",
                                "status": image_status,
                                "note": image_note,
                            },
                            "routing_summary": routing,
                        }
                    ),
                    ensure_ascii=False,
                    default=str,
                ),
            }
        )
        print(f"[INFO] row {len(review_rows)}/{len(issues_df)} -> {routing['decision_source']}")

    review_df = pd.DataFrame(review_rows)
    tech_df = pd.DataFrame(tech_rows)
    output_path = Path(args.output) if args.output else input_path.with_name(
        f"{input_path.stem}_llm_final_qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )
    _write_excel(output_path, review_df, tech_df)
    elapsed_sec = time.time() - start_time
    elapsed_min = elapsed_sec / 60.0
    print(f"[SUMMARY] elapsed={elapsed_sec:.1f}s ({elapsed_min:.1f}m), llm_calls={llm_calls}, tokens_used={total_tokens_used:,}")
    print(f"[DONE] {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
