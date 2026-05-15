#!/usr/bin/env python3
"""Build a browser-friendly HTML review report from a QV QA Excel file."""

from __future__ import annotations

import argparse
import json
import html
import os
import re
import sys
import webbrowser
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


SHEET_CANDIDATES = ("최종검토", "qa_review", "issues_with_llm", "issues")
TECH_SHEET_CANDIDATES = ("기술컨텍스트", "technical_context")
IMAGE_COL_CANDIDATES = ("이미지경로", "image_path", "screenshot_path", "llm_image_path")


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    return str(v)


def _to_int(v: Any) -> int | None:
    try:
        if v is None or pd.isna(v):
            return None
    except Exception:
        pass
    try:
        return int(float(v))
    except Exception:
        return None


def _pick_sheet(sheet_names: list[str], candidates: tuple[str, ...]) -> str:
    for cand in candidates:
        if cand in sheet_names:
            return cand
    return sheet_names[0]


def _first_value(row: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        if key in row:
            value = row.get(key)
            if value is not None and not (isinstance(value, float) and pd.isna(value)):
                if str(value).strip() != "":
                    return value
    return default


def _normalize_text(value: Any) -> str:
    return " ".join(_to_str(value).split())


def _slugify(value: Any) -> str:
    text = _to_str(value)
    text = re.sub(r"[^0-9A-Za-z_]+", "_", text)
    return text.strip("_")


def _split_paths(value: Any) -> list[Path]:
    text = _to_str(value).strip()
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"[|;\n]", text) if p.strip()]
    paths: list[Path] = []
    for part in parts:
        paths.append(Path(part))
    return paths


def _resolve_existing_path(path: Path, excel_dir: Path, excel_stem_dir: Path) -> Path | None:
    candidates = [path]
    if not path.is_absolute():
        candidates.extend([excel_dir / path, excel_stem_dir / path])
    for cand in candidates:
        try:
            if cand.exists():
                return cand.resolve()
        except Exception:
            continue
    return None


def _resolve_from_row(row: dict[str, Any], excel_path: Path) -> list[Path]:
    excel_dir = excel_path.parent
    image_dir = excel_dir / excel_path.stem
    paths: list[Path] = []

    for col in IMAGE_COL_CANDIDATES:
        for raw in _split_paths(row.get(col)):
            found = _resolve_existing_path(raw, excel_dir, image_dir)
            if found and found not in paths:
                paths.append(found)

    if paths:
        return paths

    if not image_dir.exists():
        return []

    row_no = _to_int(_first_value(row, ("행번호", "row_index")))
    if row_no is None:
        row_no = _to_int(row.get("_row_number"))
    frame = _to_int(_first_value(row, ("프레임", "frame")))
    rule = _slugify(_first_value(row, ("Issue Rule", "규칙", "rule")))

    exts = ("jpg", "jpeg", "png", "webp")
    patterns: list[str] = []
    if row_no is not None and frame is not None and rule:
        patterns.extend(
            [
                f"row_{row_no:04d}_frame_{frame:08d}_*.{{ext}}",
                f"*row_{row_no:04d}*frame_{frame:08d}*{rule}*.{{ext}}",
            ]
        )
    if frame is not None and rule:
        patterns.append(f"*frame_{frame:08d}*{rule}*.{{ext}}")
    if row_no is not None:
        patterns.append(f"row_{row_no:04d}*.{{ext}}")
    if frame is not None:
        patterns.append(f"*frame_{frame:08d}*.{{ext}}")

    for pat in patterns:
        for ext in exts:
            for match in sorted(image_dir.glob(pat.format(ext=ext))):
                if match not in paths:
                    paths.append(match.resolve())
        if paths:
            break

    return paths


def _pick_image_src(image_path: Path, output_dir: Path) -> str:
    try:
        rel = os.path.relpath(str(image_path), start=str(output_dir))
        if not rel.startswith(".."):
            return Path(rel).as_posix()
    except Exception:
        pass
    try:
        return image_path.resolve().as_uri()
    except Exception:
        return str(image_path.resolve())


def _load_workbook(input_path: Path, sheet_name: str | None) -> tuple[pd.DataFrame, pd.DataFrame | None, str]:
    xls = pd.ExcelFile(input_path)
    review_sheet = sheet_name or _pick_sheet(xls.sheet_names, SHEET_CANDIDATES)
    review_df = pd.read_excel(input_path, sheet_name=review_sheet)
    tech_df = None
    tech_sheet = next((s for s in TECH_SHEET_CANDIDATES if s in xls.sheet_names), None)
    if tech_sheet:
        tech_df = pd.read_excel(input_path, sheet_name=tech_sheet)
    return review_df, tech_df, review_sheet


def _build_merge_lookup(tech_df: pd.DataFrame | None) -> dict[int, dict[str, Any]]:
    if tech_df is None or tech_df.empty:
        return {}
    row_col = None
    for cand in ("행번호", "row_index"):
        if cand in tech_df.columns:
            row_col = cand
            break
    if row_col is None:
        return {}
    lookup: dict[int, dict[str, Any]] = {}
    for _, row in tech_df.iterrows():
        row_no = _to_int(row.get(row_col))
        if row_no is None:
            continue
        lookup[row_no] = row.to_dict()
    return lookup


def _parse_context_json(value: Any) -> dict[str, Any]:
    text = _to_str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _series_value_from_obj(obj: dict[str, Any], signal_key: str) -> Any:
    if not obj:
        return None
    key = signal_key.lower()
    if key == "ttc":
        inv_ttc = obj.get("inv_ttc")
        try:
            inv_ttc_f = float(inv_ttc)
            if inv_ttc_f != 0:
                return abs(1.0 / inv_ttc_f)
        except Exception:
            pass
        return obj.get("ttc_from_inv_ttc")
    if key in {"long_dist", "long distance [m]"}:
        return obj.get("long_dist")
    if key in {"lat_dist", "lateral distance [m]"}:
        return obj.get("lat_dist")
    if key in {"abs_long_vel", "absolute longitudinal velocity [m/s]"}:
        return obj.get("abs_long_vel")
    if key in {"abs_lat_vel", "absolute lateral velocity [m/s]"}:
        return obj.get("abs_lat_vel")
    if key in {"existence_prob", "existence probability"}:
        return obj.get("existence_prob")
    if key in {"lane_assignment", "lane position"}:
        return obj.get("lane_assignment")
    return obj.get(signal_key)


def _signal_series(rec: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    ctx = _parse_context_json(rec.get("qv_context_json") or rec.get("technical_context") or rec.get("context_json"))
    obj_prev = ctx.get("target_object_prev") or {}
    obj_curr = ctx.get("target_object_curr") or {}
    obj_next = ctx.get("target_object_next") or {}
    issue_signal = _normalize_text(_first_value(rec, ("Primary Signal", "Issue Signal", "문제신호", "problem_signal")))
    issue_signal_lower = issue_signal.lower()

    signal_key = "ttc"
    if "lat error" in issue_signal_lower or "lateral" in issue_signal_lower or "횡" in issue_signal_lower:
        signal_key = "lat_dist"
    elif "long error" in issue_signal_lower or "longitudinal" in issue_signal_lower or "distance" in issue_signal_lower or "거리" in issue_signal_lower:
        signal_key = "long_dist"
    elif "heading" in issue_signal_lower or "yaw" in issue_signal_lower:
        signal_key = "heading"
    elif "velocity" in issue_signal_lower or "속도" in issue_signal_lower:
        if "lateral" in issue_signal_lower or "횡" in issue_signal_lower:
            signal_key = "abs_lat_vel"
        else:
            signal_key = "abs_long_vel"
    elif "probability" in issue_signal_lower or "존재" in issue_signal_lower:
        signal_key = "existence_prob"
    elif "lane" in issue_signal_lower or "차선" in issue_signal_lower:
        signal_key = "lane_assignment"

    signal_label = {
        "ttc": "TTC [s]",
        "long_dist": "Long Distance [m]",
        "lat_dist": "Lateral Distance [m]",
        "abs_long_vel": "Absolute Longitudinal Velocity [m/s]",
        "abs_lat_vel": "Absolute Lateral Velocity [m/s]",
        "existence_prob": "Existence Probability",
        "lane_assignment": "Lane Position",
        "heading": "Heading",
    }.get(signal_key, "Issue Signal")

    frames = [
        ("-1", obj_prev),
        ("0", obj_curr),
        ("+1", obj_next),
    ]
    series: list[dict[str, Any]] = []
    for offset, obj in frames:
        series.append(
            {
                "offset": offset,
                "value": _series_value_from_obj(obj, signal_key),
                "frame": _first_value(rec, ("프레임", "frame")),
            }
        )
    return signal_label, series


def _render_signal_timeline(series: list[dict[str, Any]], label: str) -> str:
    values = [s.get("value") for s in series]
    numeric = []
    for v in values:
        try:
            numeric.append(float(v))
        except Exception:
            numeric.append(None)

    if all(v is None for v in numeric):
        rows = []
        for item in series:
            rows.append(
                f"<div class='timeline-row'><span>{html.escape(str(item.get('offset')))}</span><strong>{html.escape(_to_str(item.get('value')) or '-')}</strong></div>"
            )
        return f"<div class='timeline timeline-text'><div class='timeline-title'>{html.escape(label)} timeline</div>{''.join(rows)}</div>"

    valid_vals = [v for v in numeric if v is not None]
    if not valid_vals:
        return "<div class='timeline-empty'>차트를 만들 수 없습니다.</div>"
    min_v = min(valid_vals)
    max_v = max(valid_vals)
    span = max(max_v - min_v, 1e-6)
    width = 320
    height = 130
    points = []
    for idx, v in enumerate(numeric):
        if v is None:
            continue
        x = 30 + idx * 120
        y = 100 - ((v - min_v) / span) * 70
        points.append((x, y))

    polyline = " ".join(f"{x},{y}" for x, y in points)
    dots = []
    for idx, v in enumerate(numeric):
        if v is None:
            continue
        x = 30 + idx * 120
        y = 100 - ((v - min_v) / span) * 70
        dots.append(
            f"<circle cx='{x}' cy='{y}' r='5.5' fill='#7dd3fc' stroke='white' stroke-width='1.5' />"
            f"<text x='{x}' y='{y - 12}' text-anchor='middle' fill='#edf2ff' font-size='11'>{html.escape(_to_str(v))}</text>"
            f"<text x='{x}' y='122' text-anchor='middle' fill='#a5b4d4' font-size='11'>{html.escape(str(series[idx].get('offset')))}</text>"
        )
    return f"""
    <div class="timeline">
      <div class="timeline-title">{html.escape(label)} timeline</div>
      <svg viewBox="0 0 {width} {height}" class="timeline-svg" aria-label="{html.escape(label)} timeline">
        <line x1="20" y1="100" x2="300" y2="100" stroke="rgba(255,255,255,0.14)" stroke-width="1"/>
        <polyline points="{polyline}" fill="none" stroke="#7dd3fc" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        {''.join(dots)}
      </svg>
    </div>
    """


def _count_values(records: list[dict[str, Any]], keys: tuple[str, ...]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for rec in records:
        value = _first_value(rec, keys)
        value_str = _normalize_text(value)
        if value_str:
            counter[value_str] += 1
    return counter


def _render_summary_cards(counter: Counter[str]) -> str:
    total = sum(counter.values())
    if total == 0:
        return "<div class='empty-note'>표시할 요약 정보가 없습니다.</div>"
    items = []
    for label, value in counter.most_common():
        pct = (value / total) * 100 if total else 0
        items.append(
            f"""
            <div class="summary-card">
              <div class="summary-label">{html.escape(label)}</div>
              <div class="summary-value">{value}</div>
              <div class="summary-bar"><span style="width:{pct:.1f}%"></span></div>
            </div>
            """
        )
    return "\n".join(items)


def _render_image_gallery(image_paths: list[Path], output_dir: Path) -> str:
    if not image_paths:
        return "<div class='image-empty'>이미지 없음</div>"
    blocks = []
    for path in image_paths[:3]:
        src = _pick_image_src(path, output_dir)
        blocks.append(
            f"""
            <figure class="image-figure">
              <img src="{html.escape(src)}" alt="{html.escape(path.name)}" loading="lazy" />
              <figcaption>{html.escape(path.name)}</figcaption>
            </figure>
            """
        )
    return "\n".join(blocks)


def _compact_kv(title: str, value: Any) -> str:
    text = _to_str(value)
    if not text:
        text = "-"
    return f"<div class='kv'><span>{html.escape(title)}</span><strong>{html.escape(text)}</strong></div>"


def _metric(label: str, value: Any, tone: str = "") -> str:
    value_text = _to_str(value) or "-"
    tone_class = f" {tone}" if tone else ""
    return f"<div class='metric{tone_class}'><span>{html.escape(label)}</span><strong>{html.escape(value_text)}</strong></div>"


def _is_fn_issue(rec: dict[str, Any]) -> bool:
    rule = _normalize_text(_first_value(rec, ("Issue Rule", "규칙", "rule"))).upper()
    issue_type = _normalize_text(_first_value(rec, ("이슈유형", "issue_type"))).lower()
    return "FN" in rule or "fn" in issue_type


def _is_lidar_comparison_issue(rec: dict[str, Any]) -> bool:
    rule = _normalize_text(_first_value(rec, ("Issue Rule", "규칙", "rule"))).upper()
    issue_type = _normalize_text(_first_value(rec, ("이슈유형", "issue_type"))).lower()
    if "LIDAR" not in rule and "lidar" not in issue_type:
        return False
    return any(token in rule for token in ("DISTANCE", "SPEED")) or any(token in issue_type for token in ("distance", "speed", "dist", "vel"))


def _is_od_ttc_risk(rec: dict[str, Any]) -> bool:
    rule = _normalize_text(_first_value(rec, ("Issue Rule", "규칙", "rule"))).upper()
    issue_type = _normalize_text(_first_value(rec, ("이슈유형", "issue_type"))).lower()
    return "OD_TTC_RISK" in rule or ("ttc" in issue_type and "od" in rule.lower())


def _is_od_heading_change(rec: dict[str, Any]) -> bool:
    rule = _normalize_text(_first_value(rec, ("Issue Rule", "규칙", "rule"))).upper()
    issue_type = _normalize_text(_first_value(rec, ("이슈유형", "issue_type"))).lower()
    return "OD_HEADING_CHANGE" in rule or "heading" in issue_type


def _format_signal_jump(rec: dict[str, Any], series: list[dict[str, Any]]) -> str:
    prev = _first_value(rec, ("previous_value", "Prev Frame Value", "이전값", "원본이전값"))
    curr = _first_value(rec, ("current_value", "Issue Signal Value", "원본현재값"))
    if (prev is None or _to_str(prev) == "") and series:
        prev = series[0].get("value")
    if (curr is None or _to_str(curr) == "") and len(series) > 1:
        curr = series[1].get("value")
    prev_text = _to_str(prev)
    curr_text = _to_str(curr)
    if not prev_text or not curr_text or prev_text.upper() == "N/A" or curr_text.upper() == "N/A":
        return ""
    try:
        delta = float(curr) - float(prev)
        return f"Prev {float(prev):.2f} -> Curr {float(curr):.2f} (Δ {delta:+.2f})"
    except Exception:
        if prev_text != curr_text:
            return f"Prev {prev_text} -> Curr {curr_text}"
    return ""


def _friendly_rule_name(rule: str, issue_type: str = "", primary_signal: str = "") -> str:
    rule_u = _normalize_text(rule).upper()
    issue_l = _normalize_text(issue_type).lower()
    signal_l = _normalize_text(primary_signal).lower()
    mapping = {
        "ANALYSIS_LIDAR_FN": "LiDAR False Negative",
        "ANALYSIS_LIDAR_FP": "LiDAR False Positive",
        "ANALYSIS_LIDAR_DISTANCE": "LiDAR Distance Mismatch",
        "ANALYSIS_LIDAR_SPEED": "LiDAR Velocity Mismatch",
        "ANALYSIS_OD_TTC_RISK": "OD TTC Risk",
        "ANALYSIS_OD_HEADING_CHANGE": "OD Heading Jump",
        "ANALYSIS_OD_ID_DUPLICATION": "OD ID Duplication",
    }
    if rule_u in mapping:
        return mapping[rule_u]
    if "lidar" in rule_u.lower() and "fn" in issue_l:
        return "LiDAR False Negative"
    if "lidar" in rule_u.lower() and "fp" in issue_l:
        return "LiDAR False Positive"
    if "long error" in signal_l:
        return "Longitudinal Distance Mismatch"
    if "lat error" in signal_l:
        return "Lateral Distance Mismatch"
    text = rule_u.replace("ANALYSIS_", "").replace("_", " ").title()
    return text or "Issue"


def _decision_tone(decision: str) -> str:
    if decision == "실제 이슈":
        return "real"
    if decision == "우선순위 낮은 이슈":
        return "low"
    if decision == "이슈 아님":
        return "none"
    if "실패" in decision:
        return "fail"
    return "neutral"


def _render_issue_cards(records: list[dict[str, Any]], excel_path: Path, output_dir: Path) -> str:
    cards = []
    for rec in records:
        decision = _normalize_text(_first_value(rec, ("판정결과", "final_decision")))
        priority = _normalize_text(_first_value(rec, ("우선순위(1~5)", "priority_1_to_5")))
        mode = _normalize_text(_first_value(rec, ("Decision Mode", "판정방식", "decision_source")))
        row_no = _normalize_text(_first_value(rec, ("행번호", "row_index")))
        issue_rule = _normalize_text(_first_value(rec, ("Issue Rule", "규칙", "rule")))
        issue_signal = _normalize_text(_first_value(rec, ("Issue Signal", "문제신호", "problem_signal")))
        dataset = _normalize_text(_first_value(rec, ("데이터셋", "dataset")))
        frame = _normalize_text(_first_value(rec, ("프레임", "frame")))
        issue_type = _normalize_text(_first_value(rec, ("이슈유형", "issue_type")))
        role = _normalize_text(_first_value(rec, ("Role", "role")))
        rule_priority = _normalize_text(_first_value(rec, ("Rule Priority(1~5)", "priority")))
        object_id = _normalize_text(_first_value(rec, ("객체ID", "object_id")))
        primary_signal = _normalize_text(_first_value(rec, ("Primary Signal", "Issue Signal", "문제신호", "problem_signal")))
        signal_value = _normalize_text(_first_value(rec, ("Issue Signal Value", "원본현재값", "current_value")))
        delta_vs_lidar = _normalize_text(_first_value(rec, ("Delta vs Lidar", "신호오차요약")))
        long_dist = _normalize_text(_first_value(rec, ("Long Distance [m]", "long_dist")))
        lat_dist = _normalize_text(_first_value(rec, ("Lateral Distance [m]", "lat_dist")))
        lidar_long = _normalize_text(_first_value(rec, ("Lidar Long [m]", "lidar_long")))
        lidar_lat = _normalize_text(_first_value(rec, ("Lidar Lat [m]", "lidar_lat")))
        ttc = _normalize_text(_first_value(rec, ("TTC [s]", "ttc")))
        summary = _normalize_text(_first_value(rec, ("이슈요약", "issue_summary")))
        final_reason = _normalize_text(_first_value(rec, ("최종판단", "final_reasoning")))
        pre_reason = _normalize_text(_first_value(rec, ("사전판단이유",)))
        llm_need_reason = _normalize_text(_first_value(rec, ("LLM필요사유",)))
        llm_result_summary = _normalize_text(_first_value(rec, ("LLM결과요약", "final_reasoning")))
        rule_basis = _normalize_text(_first_value(rec, ("룰기반근거", "rule_trigger_basis")))
        referenced = _normalize_text(_first_value(rec, ("참조데이터", "referenced_data")))
        routing_reason = _normalize_text(_first_value(rec, ("Routing Reason", "라우팅사유", "routing_reason")))
        non_issue = _normalize_text(_first_value(rec, ("비이슈사유", "non_issue_reason")))
        action = _normalize_text(_first_value(rec, ("권고조치", "recommended_action")))
        llm_error = _normalize_text(_first_value(rec, ("LLM오류", "llm_error")))
        confidence = _normalize_text(_first_value(rec, ("신뢰도(0~1)", "confidence_0_to_1")))
        confidence_value = _normalize_text(_first_value(rec, ("신뢰도(0~1)", "confidence_0_to_1")))
        signal_delta = delta_vs_lidar
        _signal_label, signal_series = _signal_series(rec)
        current_signal_value = signal_value or (signal_series[1].get("value") if len(signal_series) > 1 else "")
        llm_tag = "LLM 판정" if mode == "LLM 판정" else ("LLM 실패" if "실패" in mode else "사전 판정")
        fn_issue = _is_fn_issue(rec)
        lidar_comparison_issue = _is_lidar_comparison_issue(rec)
        od_ttc_risk = _is_od_ttc_risk(rec)
        od_heading_change = _is_od_heading_change(rec)
        friendly_title = _friendly_rule_name(issue_rule, issue_type, primary_signal or issue_signal)
        decision_tone = _decision_tone(decision)
        signal_jump = _format_signal_jump(rec, signal_series)
        display_delta = signal_delta if signal_delta and not fn_issue else signal_jump
        if fn_issue:
            signal_delta_html = ""
        elif lidar_comparison_issue and signal_delta:
            signal_delta_html = _metric("LiDAR 대비 오차", signal_delta, "accent")
        elif (od_ttc_risk or od_heading_change) and signal_jump:
            signal_delta_html = _metric("이전 프레임 대비 점프", signal_jump, "accent")
        else:
            signal_delta_html = ""
        llm_result_display = "" if mode == "사전 판정" else (llm_result_summary or final_reason)

        image_paths = [Path(p) for p in rec.get("_image_paths", [])]
        if not image_paths:
            image_paths = _resolve_from_row(rec, excel_path)

        search_text = " ".join(
            [
                row_no,
                dataset,
                frame,
                issue_rule,
                issue_signal,
                decision,
                priority,
                mode,
                summary,
                final_reason,
                rule_basis,
                referenced,
                routing_reason,
                non_issue,
                action,
                llm_error,
                confidence,
                issue_type,
                role,
                rule_priority,
                object_id,
                signal_delta,
                signal_jump,
                primary_signal,
                signal_value,
                llm_tag,
            ]
        ).lower()

        badge_class = {
            "실제 이슈": "badge real",
            "우선순위 낮은 이슈": "badge low",
            "이슈 아님": "badge none",
            "LLM 판정 실패": "badge fail",
            "판단 보류": "badge hold",
        }.get(decision, "badge neutral")

        context_metrics = "".join(
            [
                _metric("데이터셋", dataset),
                _metric("프레임", frame),
                _metric("객체 ID", object_id),
                _metric("Role", role),
            ]
        )
        priority_metrics = "".join(
            [
                _metric("룰 우선순위", f"P{rule_priority}" if rule_priority else "-"),
                _metric("LLM 우선순위", f"P{priority}" if priority else "-"),
                _metric("판정 방식", llm_tag),
                _metric("신뢰도", confidence_value),
            ]
        )
        signal_metrics = "".join(
            [
                _metric("문제 신호", primary_signal or issue_signal),
                _metric("신호 값", current_signal_value),
                signal_delta_html,
                _metric("OD Long / Lat", f"{long_dist or '-'} / {lat_dist or '-'}"),
                _metric("LiDAR Long / Lat", f"{lidar_long or '-'} / {lidar_lat or '-'}") if lidar_comparison_issue else "",
                _metric("TTC", ttc),
            ]
        )

        cards.append(
            f"""
            <article id="row-{html.escape(row_no)}" class="issue-card" data-status="{html.escape(decision)}" data-mode="{html.escape(mode)}" data-search="{html.escape(search_text)}">
              <div class="card-top">
                <div>
                  <div class="card-kicker">{html.escape(dataset)} · frame {html.escape(frame)} · object {html.escape(object_id)}</div>
                  <div class="card-title">{html.escape(friendly_title)}</div>
                  <div class="card-subtitle">{html.escape(issue_rule or '-')} · {html.escape(issue_type or '-')}</div>
                </div>
                <div class="badge-row">
                  <span class="{badge_class}">{html.escape(decision or '-')}</span>
                  <span class="badge mode">{html.escape(mode or '-')}</span>
                </div>
              </div>

              <div class="judgment-strip {html.escape(decision_tone)}">
                <div>
                  <span>최종 이슈 판단</span>
                  <strong>{html.escape(decision or '-')}</strong>
                </div>
                <div>
                  <span>최종 우선순위</span>
                  <strong>P{html.escape(priority or '-')}</strong>
                </div>
                <div>
                  <span>룰 우선순위</span>
                  <strong>P{html.escape(rule_priority or '-')}</strong>
                </div>
              </div>

              <div class="evidence-strip">
                <div>
                  <span>Signal</span>
                  <strong>{html.escape(primary_signal or issue_signal or '-')}</strong>
                </div>
                <div>
                  <span>Value</span>
                  <strong>{html.escape(_to_str(current_signal_value) or '-')}</strong>
                </div>
                <div>
                  <span>Delta</span>
                  <strong>{html.escape(display_delta if display_delta and not fn_issue else ('미검출 이슈' if fn_issue else '-'))}</strong>
                </div>
              </div>

              <div class="card-grid">
                <section class="image-panel">
                  <div class="image-gallery image-gallery-large">
                    { _render_image_gallery(image_paths, output_dir) }
                  </div>
                  <div class="info-section">
                    <h3>Context</h3>
                    <div class="metric-grid">{context_metrics}</div>
                  </div>
                </section>

                <section class="info-panel">
                  <div class="info-section">
                    <h3>Priority</h3>
                    <div class="metric-grid">{priority_metrics}</div>
                  </div>

                  <div class="info-section">
                    <h3>Signal Evidence</h3>
                    <div class="metric-grid">{signal_metrics}</div>
                  </div>

                  <div class="text-block">
                    <label>사전 판단 이유</label>
                    <p>{html.escape(pre_reason or routing_reason or summary or '-')}</p>
                  </div>
                  <div class="text-block">
                    <label>LLM 필요 사유</label>
                    <p>{html.escape(llm_need_reason or ('사전 판단으로 처리되어 LLM 재검토를 생략했습니다.' if mode == '사전 판정' else '경계 조건 검토를 위해 LLM 분석이 필요했습니다.'))}</p>
                  </div>
                  <div class="text-block">
                    <label>LLM 결과</label>
                    <p>{html.escape(llm_result_display)}</p>
                  </div>
                </section>
              </div>
            </article>
            """
        )
    return "\n".join(cards)


def _render_sidebar(records: list[dict[str, Any]]) -> str:
    items = []
    for rec in records:
        row_no = _normalize_text(_first_value(rec, ("행번호", "row_index")))
        decision = _normalize_text(_first_value(rec, ("판정결과", "final_decision")))
        mode = _normalize_text(_first_value(rec, ("Decision Mode", "판정방식", "decision_source")))
        issue_rule = _normalize_text(_first_value(rec, ("Issue Rule", "규칙", "rule")))
        dataset = _normalize_text(_first_value(rec, ("데이터셋", "dataset")))
        frame = _normalize_text(_first_value(rec, ("프레임", "frame")))
        priority = _normalize_text(_first_value(rec, ("우선순위(1~5)", "priority_1_to_5")))
        llm_tag = "LLM" if mode == "LLM 판정" else ("FAIL" if "실패" in mode else "AUTO")
        badge_class = {
            "실제 이슈": "side-badge real",
            "우선순위 낮은 이슈": "side-badge low",
            "이슈 아님": "side-badge none",
            "LLM 판정 실패": "side-badge fail",
            "판단 보류": "side-badge hold",
        }.get(decision, "side-badge neutral")
        items.append(
            f"""
            <a class="nav-item" href="#row-{html.escape(row_no)}" data-target="row-{html.escape(row_no)}">
              <span class="nav-top"><strong>{html.escape(frame or '-')}</strong><em>{html.escape(llm_tag)}</em></span>
              <span class="nav-meta">{html.escape(dataset or '-')}</span>
              <span class="{badge_class}">{html.escape(decision or '-')} · P{html.escape(priority or '-')}</span>
              <span class="nav-rule">{html.escape(issue_rule or '-')}</span>
            </a>
            """
        )
    return "\n".join(items)


def _render_html(records: list[dict[str, Any]], output_path: Path, source_sheet: str, excel_path: Path) -> str:
    decisions = Counter(_normalize_text(_first_value(rec, ("판정결과", "final_decision"))) or "미정" for rec in records)
    modes = Counter(_normalize_text(_first_value(rec, ("Decision Mode", "판정방식", "decision_source"))) or "미정" for rec in records)
    signals = Counter(_normalize_text(_first_value(rec, ("Issue Signal", "문제신호", "problem_signal"))) or "미정" for rec in records)
    total = len(records)
    image_count = sum(1 for rec in records if rec.get("_image_paths"))
    decision_cards = "".join(
        f"""
        <div class="metric-card">
          <div class="metric-label">{html.escape(label)}</div>
          <div class="metric-value">{count}</div>
        </div>
        """
        for label, count in [
            ("총 이슈", total),
            ("실제 이슈", decisions.get("실제 이슈", 0)),
            ("저우선순위", decisions.get("우선순위 낮은 이슈", 0)),
            ("이슈 아님", decisions.get("이슈 아님", 0)),
            ("LLM 실패", decisions.get("LLM 판정 실패", 0)),
            ("이미지 있음", image_count),
            ("LLM 검토", modes.get("LLM 판정", 0)),
            ("사전 판정", modes.get("사전 판정", 0)),
        ]
    )

    decision_tabs = ["전체"] + [label for label in decisions.keys()]
    tab_buttons = "".join(
        f'<button class="filter-btn{" active" if i == 0 else ""}" data-filter="{html.escape(tab)}">{html.escape(tab)}</button>'
        for i, tab in enumerate(decision_tabs)
    )

    top_signals = "".join(
        f'<span class="chip">{html.escape(sig)} <strong>{count}</strong></span>' for sig, count in signals.most_common(8)
    )

    cards = _render_issue_cards(records, excel_path, output_path.parent)
    sidebar = _render_sidebar(records)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QV Issue Review Report</title>
  <style>
    :root {{
      --bg: #0b1020;
      --bg2: #101936;
      --panel: rgba(16, 25, 54, 0.86);
      --panel-2: rgba(15, 22, 42, 0.92);
      --border: rgba(255,255,255,0.08);
      --text: #edf2ff;
      --muted: #a5b4d4;
      --accent: #7dd3fc;
      --good: #36d399;
      --warn: #fbbf24;
      --bad: #fb7185;
      --neutral: #94a3b8;
      --shadow: 0 18px 50px rgba(0,0,0,0.35);
      --radius: 20px;
      --radius-sm: 14px;
      font-synthesis-weight: none;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Aptos", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(125, 211, 252, 0.2), transparent 30%),
        radial-gradient(circle at top right, rgba(99, 102, 241, 0.18), transparent 25%),
        linear-gradient(180deg, var(--bg), #070b16 70%);
    }}
    .wrap {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    .page-layout {{
      display: grid;
      grid-template-columns: 240px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
      margin-top: 18px;
    }}
    .side-nav {{
      position: sticky;
      top: 20px;
      max-height: calc(100vh - 40px);
      overflow: auto;
      padding: 14px;
      border-radius: 22px;
      border: 1px solid var(--border);
      background: rgba(10, 16, 32, 0.82);
      box-shadow: var(--shadow);
    }}
    .side-nav-title {{
      font-size: 14px;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin: 0 0 12px;
      color: var(--accent);
    }}
    .nav-item {{
      display: grid;
      gap: 6px;
      padding: 10px 12px;
      margin-bottom: 8px;
      border-radius: 16px;
      border: 1px solid rgba(255,255,255,0.07);
      background: rgba(255,255,255,0.03);
      text-decoration: none;
      color: var(--text);
      transition: transform 0.15s ease, border-color 0.15s ease;
    }}
    .nav-item:hover {{ transform: translateX(2px); border-color: rgba(125, 211, 252, 0.28); }}
    .nav-row {{ font-size: 13px; color: var(--accent); font-weight: 700; }}
    .nav-rule {{
      font-size: 12px;
      color: var(--muted);
      line-height: 1.35;
    }}
    .side-badge {{
      display: inline-flex;
      width: fit-content;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 11px;
      border: 1px solid transparent;
    }}
    .side-badge.real {{ background: rgba(54, 211, 153, 0.16); color: #b7f7df; border-color: rgba(54, 211, 153, 0.22); }}
    .side-badge.low {{ background: rgba(251, 191, 36, 0.16); color: #fde68a; border-color: rgba(251, 191, 36, 0.22); }}
    .side-badge.none {{ background: rgba(148, 163, 184, 0.16); color: #d9e2f0; border-color: rgba(148, 163, 184, 0.22); }}
    .side-badge.fail {{ background: rgba(251, 113, 133, 0.16); color: #fecdd3; border-color: rgba(251, 113, 133, 0.22); }}
    .side-badge.hold, .side-badge.neutral {{ background: rgba(125, 211, 252, 0.12); color: #cffafe; border-color: rgba(125, 211, 252, 0.18); }}
    .content {{
      min-width: 0;
    }}
    .hero {{
      position: relative;
      padding: 28px;
      border: 1px solid var(--border);
      border-radius: 28px;
      background: linear-gradient(135deg, rgba(16,25,54,0.96), rgba(10,16,32,0.92));
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(125, 211, 252, 0.08), transparent 45%, rgba(99, 102, 241, 0.08));
      pointer-events: none;
    }}
    .title {{
      font-size: clamp(30px, 3.5vw, 48px);
      line-height: 1.05;
      margin: 0 0 10px;
      letter-spacing: -0.04em;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 15px;
      max-width: 980px;
    }}
    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .meta-pill, .chip, .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      padding: 8px 12px;
      font-size: 13px;
      line-height: 1;
      background: rgba(255,255,255,0.04);
      color: var(--text);
    }}
    .badge-row {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
    .badge.real {{ background: rgba(54, 211, 153, 0.16); color: #b7f7df; border-color: rgba(54, 211, 153, 0.3); }}
    .badge.low {{ background: rgba(251, 191, 36, 0.16); color: #fde68a; border-color: rgba(251, 191, 36, 0.3); }}
    .badge.none {{ background: rgba(148, 163, 184, 0.16); color: #d9e2f0; border-color: rgba(148, 163, 184, 0.3); }}
    .badge.fail {{ background: rgba(251, 113, 133, 0.16); color: #fecdd3; border-color: rgba(251, 113, 133, 0.3); }}
    .badge.hold, .badge.neutral, .badge.priority, .badge.mode {{
      color: var(--text);
    }}
    .badge.priority {{ background: rgba(125, 211, 252, 0.14); border-color: rgba(125, 211, 252, 0.3); }}
    .badge.mode {{ background: rgba(99, 102, 241, 0.16); border-color: rgba(99, 102, 241, 0.28); }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
      margin: 20px 0 10px;
    }}
    .summary-card, .metric-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 14px 16px;
      box-shadow: var(--shadow);
    }}
    .metric-card {{
      min-height: 92px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .summary-label, .metric-label {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .summary-value, .metric-value {{
      font-size: 28px;
      font-weight: 700;
      letter-spacing: -0.04em;
    }}
    .summary-bar {{
      height: 8px;
      background: rgba(255,255,255,0.06);
      border-radius: 999px;
      margin-top: 10px;
      overflow: hidden;
    }}
    .summary-bar span {{
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), #818cf8);
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
      margin: 22px 0 12px;
    }}
    .filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .filter-btn {{
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      border-radius: 999px;
      padding: 10px 14px;
      font-size: 14px;
      cursor: pointer;
      transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease;
    }}
    .filter-btn:hover {{ transform: translateY(-1px); border-color: rgba(125, 211, 252, 0.35); }}
    .filter-btn.active {{ background: rgba(125, 211, 252, 0.16); border-color: rgba(125, 211, 252, 0.35); }}
    .search {{
      min-width: min(100%, 340px);
      display: flex;
      gap: 8px;
      align-items: center;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(255,255,255,0.04);
    }}
    .search input {{
      width: 100%;
      border: 0;
      background: transparent;
      color: var(--text);
      outline: none;
      font-size: 14px;
    }}
    .chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 12px 0 20px;
    }}
    .chip strong {{
      color: var(--accent);
      font-weight: 700;
    }}
    .section-title {{
      margin: 28px 0 12px;
      font-size: 18px;
      letter-spacing: -0.02em;
    }}
    .issue-card {{
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 18px;
      margin-bottom: 18px;
      box-shadow: var(--shadow);
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 16px;
    }}
    .card-title {{
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.03em;
      margin-bottom: 6px;
    }}
    .card-subtitle {{
      color: var(--muted);
      font-size: 13px;
    }}
    .card-grid {{
      display: grid;
      grid-template-columns: minmax(460px, 1.25fr) minmax(360px, 0.95fr);
      gap: 16px;
      align-items: start;
    }}
    .image-panel, .info-panel {{
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 18px;
      padding: 14px;
    }}
    .image-panel {{
      display: grid;
      gap: 12px;
    }}
    .image-gallery-large {{
      display: grid;
      gap: 12px;
    }}
    .image-gallery-large .image-figure img {{
      min-height: 280px;
      max-height: 420px;
      object-fit: contain;
      background: #050913;
    }}
    .signal-visual {{
      padding: 12px;
      border-radius: 16px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .signal-title {{
      font-weight: 700;
      font-size: 13px;
      margin-bottom: 10px;
      color: var(--accent);
    }}
    .timeline {{
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
      padding: 10px;
    }}
    .timeline-title {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .timeline-svg {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .timeline-text {{
      display: grid;
      gap: 8px;
    }}
    .timeline-row {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 12px;
      color: var(--text);
      padding: 8px 10px;
      border-radius: 12px;
      background: rgba(255,255,255,0.04);
    }}
    .timeline-row span {{ color: var(--muted); }}
    .timeline-empty {{
      padding: 12px;
      color: var(--muted);
    }}
    .image-figure {{
      margin: 0;
      background: rgba(0,0,0,0.18);
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,0.08);
    }}
    .image-figure img {{
      display: block;
      width: 100%;
      height: auto;
      object-fit: cover;
      background: #09101f;
    }}
    .image-figure figcaption {{
      padding: 8px 10px;
      font-size: 12px;
      color: var(--muted);
      border-top: 1px solid rgba(255,255,255,0.06);
    }}
    .image-empty {{
      min-height: 240px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed rgba(255,255,255,0.12);
      border-radius: 16px;
      background: rgba(255,255,255,0.03);
    }}
    .kv-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}
    .kv {{
      display: flex;
      flex-direction: column;
      gap: 5px;
      border-radius: 14px;
      padding: 12px;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .kv span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .kv strong {{
      font-size: 14px;
      line-height: 1.35;
      word-break: break-word;
    }}
    .signal-chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0 14px;
    }}
    .signal-chip {{
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(125, 211, 252, 0.12);
      color: #cffafe;
      border: 1px solid rgba(125, 211, 252, 0.18);
      font-size: 12px;
    }}
    .text-block {{
      margin-bottom: 12px;
      padding: 12px;
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
    }}
    .text-block label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .text-block p {{
      margin: 0;
      white-space: pre-wrap;
      line-height: 1.55;
      word-break: break-word;
    }}
    details {{
      margin-top: 8px;
      border: 1px solid rgba(255,255,255,0.07);
      border-radius: 14px;
      background: rgba(255,255,255,0.02);
      overflow: hidden;
    }}
    summary {{
      cursor: pointer;
      list-style: none;
      padding: 12px 14px;
      color: var(--accent);
      font-weight: 600;
    }}
    details > div {{
      padding: 0 14px 14px;
    }}
    .empty-note {{
      color: var(--muted);
      border: 1px dashed rgba(255,255,255,0.15);
      border-radius: 14px;
      padding: 18px;
      background: rgba(255,255,255,0.03);
    }}
    .footer {{
      margin-top: 26px;
      color: var(--muted);
      font-size: 12px;
      text-align: center;
    }}
    @media (max-width: 1100px) {{
      .page-layout {{ grid-template-columns: 1fr; }}
      .side-nav {{ position: static; max-height: none; }}
      .summary-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .card-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 700px) {{
      .wrap {{ padding: 16px 12px 28px; }}
      .hero {{ padding: 20px; border-radius: 22px; }}
      .summary-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .kv-grid {{ grid-template-columns: 1fr; }}
      .card-top {{ flex-direction: column; }}
      .badge-row {{ justify-content: flex-start; }}
    }}
    :root {{
      --bg: #0d1117;
      --panel: #151b23;
      --panel-2: #111820;
      --border: #2f3a46;
      --text: #e6edf3;
      --muted: #8b98a8;
      --accent: #2dd4bf;
      --good: #3fb950;
      --warn: #d29922;
      --bad: #f85149;
      --shadow: 0 14px 36px rgba(0, 0, 0, 0.34);
      --radius: 8px;
      --radius-sm: 8px;
    }}
    body {{
      color: var(--text);
      background: linear-gradient(180deg, #0d1117 0%, #0b0f14 100%);
    }}
    .wrap {{ max-width: 1600px; }}
    .hero {{
      border-radius: 8px;
      background: #151b23;
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
      padding: 22px 24px;
    }}
    .hero::after {{ display: none; }}
    .title {{
      font-size: 30px;
      letter-spacing: 0;
      color: var(--text);
    }}
    .page-layout {{ grid-template-columns: 280px minmax(0, 1fr); }}
    .side-nav {{
      border-radius: 8px;
      background: #151b23;
      border-color: var(--border);
      box-shadow: var(--shadow);
    }}
    .side-nav-title {{ color: var(--text); }}
    .nav-item {{
      border-radius: 8px;
      background: #111820;
      border-color: #2f3a46;
      color: var(--text);
      gap: 5px;
    }}
    .nav-item:hover {{ transform: none; border-color: #2dd4bf; }}
    .nav-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-size: 13px;
    }}
    .nav-top strong {{ color: var(--text); }}
    .nav-top em {{
      font-style: normal;
      font-size: 11px;
      border: 1px solid #3c4856;
      border-radius: 999px;
      padding: 2px 7px;
      color: #b7c2d0;
      background: #0d1117;
    }}
    .nav-meta {{
      font-size: 11px;
      color: var(--muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .nav-rule {{ color: #9aa7b8; }}
    .metric-card, .summary-card, .issue-card, .image-panel, .info-panel, .text-block, details, .signal-visual, .timeline {{
      border-radius: 8px;
      background: #151b23;
      border-color: var(--border);
      box-shadow: none;
    }}
    .metric-card {{
      min-height: 78px;
      background: #151b23;
    }}
    .metric-value {{ font-size: 24px; letter-spacing: 0; }}
    .filter-btn, .meta-pill, .chip, .badge {{
      border-radius: 6px;
      color: var(--text);
      background: #151b23;
      border-color: var(--border);
    }}
    .filter-btn.active {{ background: rgba(45, 212, 191, 0.12); border-color: #2dd4bf; color: #ccfbf1; }}
    .search {{ border-radius: 6px; background: #111820; }}
    .search input {{ color: var(--text); }}
    .issue-card {{
      padding: 16px;
      border-left: 5px solid #94a3b8;
    }}
    .issue-card[data-status="실제 이슈"] {{ border-left-color: #0f8a5f; }}
    .issue-card[data-status="우선순위 낮은 이슈"] {{ border-left-color: #b7791f; }}
    .issue-card[data-status="이슈 아님"] {{ border-left-color: #64748b; }}
    .card-kicker {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .card-title {{
      font-size: 19px;
      letter-spacing: 0;
      color: var(--text);
    }}
    .card-grid {{ grid-template-columns: minmax(680px, 1.35fr) minmax(440px, 0.85fr); }}
    .judgment-strip {{
      display: grid;
      grid-template-columns: 1.4fr 1fr 1fr;
      gap: 10px;
      margin: 0 0 12px;
    }}
    .judgment-strip div {{
      border: 1px solid #2f3a46;
      border-radius: 8px;
      background: #0f151d;
      padding: 12px 14px;
    }}
    .judgment-strip span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }}
    .judgment-strip strong {{
      display: block;
      color: var(--text);
      font-size: 20px;
      line-height: 1.2;
    }}
    .judgment-strip.real div:first-child {{
      border-color: rgba(63, 185, 80, 0.55);
      background: rgba(63, 185, 80, 0.10);
    }}
    .judgment-strip.low div:first-child {{
      border-color: rgba(210, 153, 34, 0.55);
      background: rgba(210, 153, 34, 0.10);
    }}
    .judgment-strip.none div:first-child {{
      border-color: rgba(139, 152, 168, 0.55);
      background: rgba(139, 152, 168, 0.10);
    }}
    .judgment-strip.fail div:first-child {{
      border-color: rgba(248, 81, 73, 0.55);
      background: rgba(248, 81, 73, 0.10);
    }}
    .evidence-strip {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 0 0 14px;
    }}
    .evidence-strip div {{
      border: 1px solid #2f3a46;
      border-radius: 8px;
      background: #0f151d;
      padding: 10px 12px;
    }}
    .evidence-strip span, .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 5px;
    }}
    .evidence-strip strong, .metric strong {{
      display: block;
      color: var(--text);
      font-size: 14px;
      line-height: 1.35;
      word-break: break-word;
    }}
    .info-section {{
      border: 1px solid #2f3a46;
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 12px;
      background: #0f151d;
    }}
    .info-section h3 {{
      margin: 0 0 10px;
      font-size: 14px;
      color: var(--text);
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }}
    .metric {{
      border: 1px solid #2f3a46;
      border-radius: 8px;
      padding: 10px;
      background: #151b23;
    }}
    .metric.accent {{
      border-color: rgba(45, 212, 191, 0.55);
      background: rgba(45, 212, 191, 0.08);
    }}
    .image-gallery-large .image-figure img {{
      min-height: 520px;
      max-height: 760px;
      background: #0b0f14;
    }}
    .timeline-svg text {{ fill: #334155; }}
    .timeline-svg line {{ stroke: #cbd5e1; }}
    .timeline-svg polyline {{ stroke: #0f766e; }}
    .text-block {{ background: #0f151d; }}
    .text-block label {{ color: #b7c2d0; font-weight: 700; }}
    .side-badge.real, .badge.real {{ background: rgba(63, 185, 80, 0.15); color: #7ee787; border-color: rgba(63, 185, 80, 0.35); }}
    .side-badge.low, .badge.low {{ background: rgba(210, 153, 34, 0.16); color: #f2cc60; border-color: rgba(210, 153, 34, 0.35); }}
    .side-badge.none, .badge.none {{ background: rgba(139, 152, 168, 0.16); color: #c9d1d9; border-color: rgba(139, 152, 168, 0.35); }}
    .side-badge.fail, .badge.fail {{ background: rgba(248, 81, 73, 0.16); color: #ffb4ad; border-color: rgba(248, 81, 73, 0.35); }}
    @media (max-width: 1100px) {{
      .card-grid {{ grid-template-columns: 1fr; }}
      .evidence-strip {{ grid-template-columns: 1fr; }}
      .judgment-strip {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1 class="title">QV Issue Review Report</h1>
      <p class="subtitle">
        {html.escape(source_sheet)} 시트를 바탕으로 생성한 HTML 리뷰입니다. 각 이슈의 이미지, 판정결과, 우선순위, 근거를 한 화면에서 빠르게 검토할 수 있도록 구성했습니다.
      </p>
      <div class="meta-row">
        <span class="meta-pill">생성 시각: {html.escape(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}</span>
        <span class="meta-pill">총 이슈: {total}</span>
        <span class="meta-pill">이미지 포함: {image_count}</span>
        <span class="meta-pill">사전 판정 / LLM 검토 병행</span>
      </div>
    </header>

    <section>
      <div class="summary-grid">{decision_cards}</div>
    </section>

    <div class="page-layout">
      <aside class="side-nav">
        <div class="side-nav-title">Row Navigation</div>
        <div class="filters" id="filters">
          {tab_buttons}
        </div>
        <div style="height:10px"></div>
        <label class="search" style="min-width:0; width:100%;">
          <span>검색</span>
          <input id="searchInput" type="search" placeholder="행번호, Rule, Signal, 판단 내용 검색" />
        </label>
        <div style="height:14px"></div>
        {sidebar}
      </aside>

      <main class="content">
        <section>
          <h2 class="section-title">상위 이슈 신호</h2>
          <div class="chip-row">{top_signals or "<span class='empty-note'>집계된 신호가 없습니다.</span>"}</div>
        </section>

        <section>
          <h2 class="section-title">이슈 카드</h2>
          <div id="cardList">{cards}</div>
        </section>
      </main>
    </div>

    <div class="footer">
      HTML report generated by qv-issue-html-review
    </div>
  </div>

  <script>
    const buttons = Array.from(document.querySelectorAll('.filter-btn'));
    const cards = Array.from(document.querySelectorAll('.issue-card'));
    const searchInput = document.getElementById('searchInput');
    let activeFilter = '전체';

    function normalize(text) {{
      return (text || '').toString().toLowerCase();
    }}

    function applyFilters() {{
      const query = normalize(searchInput.value).trim();
      cards.forEach(card => {{
        const status = card.dataset.status || '';
        const searchable = card.dataset.search || '';
        const matchesFilter = activeFilter === '전체' || status === activeFilter;
        const matchesQuery = !query || searchable.includes(query);
        card.style.display = matchesFilter && matchesQuery ? '' : 'none';
      }});
    }}

    buttons.forEach(btn => {{
      btn.addEventListener('click', () => {{
        buttons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.dataset.filter || '전체';
        applyFilters();
      }});
    }});

    searchInput.addEventListener('input', applyFilters);

    document.querySelectorAll('.nav-item').forEach(item => {{
      item.addEventListener('click', () => {{
        const target = document.getElementById(item.dataset.target || '');
        if (target) {{
          setTimeout(() => target.scrollIntoView({{ behavior: 'smooth', block: 'start' }}), 50);
        }}
      }});
    }});
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build HTML review report from a QV QA Excel file")
    p.add_argument("--input", required=True, help="Input Excel path from qv-issue-qa-engineer")
    p.add_argument("--output", default=None, help="Output HTML path")
    p.add_argument("--sheet", default=None, help="Review sheet override")
    p.add_argument("--open", action="store_true", help="Open the generated HTML after writing")
    p.add_argument("--max-rows", type=int, default=None, help="Optional row cap for quick checks")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input Excel not found: {input_path}")
        return 2

    review_df, tech_df, review_sheet = _load_workbook(input_path, args.sheet)
    if args.max_rows is not None and args.max_rows >= 0:
        review_df = review_df.head(args.max_rows).copy()
    tech_lookup = _build_merge_lookup(tech_df)

    records: list[dict[str, Any]] = []
    for idx, row in review_df.iterrows():
        rec = row.to_dict()
        row_no = _to_int(_first_value(rec, ("행번호", "row_index"))) or (int(idx) + 1)
        rec["_row_number"] = row_no
        if row_no in tech_lookup:
            rec.update(tech_lookup[row_no])
        rec["_image_paths"] = [str(p) for p in _resolve_from_row(rec, input_path)]
        records.append(rec)

    output_path = Path(args.output) if args.output else input_path.with_name(f"{input_path.stem}_review.html")
    html_text = _render_html(records, output_path, review_sheet, input_path)
    output_path.write_text(html_text, encoding="utf-8")
    print(f"[DONE] {output_path}")

    if args.open:
        try:
            webbrowser.open(output_path.resolve().as_uri())
        except Exception as exc:
            print(f"[WARN] Could not open browser: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
