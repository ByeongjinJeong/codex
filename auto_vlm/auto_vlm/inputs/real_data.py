"""Discovery helpers for local raw/QV/JSON test data."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import Workbook


FRAME_JSON_RE = re.compile(r"^\d{8}\.json$")


@dataclass(frozen=True)
class DiscoveredRealData:
    qv_mp4_path: Path
    raw_h264_path: Path | None
    normalized_raw_video_path: Path | None
    json_dir: Path | None
    json_count: int


def discover_real_data(data_dir: Path) -> DiscoveredRealData:
    mp4_files = sorted(data_dir.rglob("*.mp4"), key=lambda path: path.stat().st_size, reverse=True)
    if not mp4_files:
        raise FileNotFoundError(f"no mp4 files found under {data_dir}")
    h264_files = sorted(data_dir.rglob("*.h264"), key=lambda path: path.stat().st_size, reverse=True)

    json_dirs: dict[Path, int] = {}
    for json_path in data_dir.rglob("*.json"):
        if FRAME_JSON_RE.match(json_path.name):
            json_dirs[json_path.parent] = json_dirs.get(json_path.parent, 0) + 1

    json_dir = None
    json_count = 0
    if json_dirs:
        json_dir, json_count = max(json_dirs.items(), key=lambda item: item[1])

    return DiscoveredRealData(
        qv_mp4_path=mp4_files[0],
        raw_h264_path=h264_files[0] if h264_files else None,
        normalized_raw_video_path=None,
        json_dir=json_dir,
        json_count=json_count,
    )


def write_discovered_cases_workbook(path: Path, discovered: DiscoveredRealData, sampling_frame: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "case_id",
            "video_path",
            "qv_video_path",
            "raw_video_path",
            "sampling_frame",
            "json_dir",
            "project_type",
            "focus_feature",
            "memo",
        ]
    )
    sheet.append(
        [
            "AUTO_DISCOVERED_001",
            str(discovered.qv_mp4_path),
            str(discovered.qv_mp4_path),
            str(discovered.normalized_raw_video_path or discovered.raw_h264_path or ""),
            sampling_frame,
            str(discovered.json_dir) if discovered.json_dir else "",
            "AUTO_DISCOVERED",
            "ALL",
            "auto discovered real data workbook",
        ]
    )
    workbook.save(path)
    return path
