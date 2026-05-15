#!/usr/bin/env python3
"""Dump QV-parsed issue context for a target Excel row.

Useful as a hint/debug script before running LLM triage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def _load_parser(repo_root: Path):
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from utils.data_processor_fvc import parse_single_fvc_frame  # type: ignore

    return parse_single_fvc_frame


def _find_repo_root(start: Path) -> Path | None:
    for p in [start.resolve()] + list(start.resolve().parents):
        if (p / "utils" / "data_processor_fvc.py").exists():
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--row", type=int, required=True, help="Excel data row index (0-based in issues sheet)")
    args = ap.parse_args()

    in_path = Path(args.input)
    df = pd.read_excel(in_path, sheet_name="issues")
    if args.row < 0 or args.row >= len(df):
        print(f"[ERROR] row out of range: {args.row}")
        return 2

    row = df.iloc[args.row]
    log_path = Path(str(row.get("log_path")))
    frame = int(row.get("frame"))
    obj_id = row.get("object_id")

    repo_root = _find_repo_root(Path.cwd())
    if repo_root is None:
        print("[ERROR] repo root not found")
        return 2

    parser = _load_parser(repo_root)
    curr = parser(str(log_path), frame)

    objs = curr.get("objects") or []
    target = None
    for o in objs:
        try:
            if int(float(o.get("id"))) == int(float(obj_id)):
                target = o
                break
        except Exception:
            if str(o.get("id")) == str(obj_id):
                target = o
                break

    out = {
        "row_index": args.row,
        "issue": {
            "rule": row.get("rule"),
            "issue_type": row.get("issue_type"),
            "feature": row.get("feature"),
            "frame": frame,
            "object_id": obj_id,
            "priority": row.get("priority"),
            "long_dist": row.get("long_dist"),
            "lat_dist": row.get("lat_dist"),
            "ttc": row.get("ttc"),
        },
        "qv_header": {
            "obj_cipv_id": curr.get("obj_cipv_id"),
            "obj_niv_l_id": curr.get("obj_niv_l_id"),
            "obj_niv_r_id": curr.get("obj_niv_r_id"),
            "obj_vd_cnt": curr.get("obj_vd_cnt"),
        },
        "target_object": target,
        "objects_count": len(objs),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
