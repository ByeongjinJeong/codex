"""Raw source video conversion helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from auto_vlm.inputs.real_data import DiscoveredRealData


def normalize_raw_video(discovered: DiscoveredRealData, output_dir: Path, fps: float = 30.0) -> DiscoveredRealData:
    if discovered.raw_h264_path is None:
        return discovered

    normalized_dir = output_dir / "raw_video_cache"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = normalized_dir / f"{discovered.raw_h264_path.stem}.raw.mp4"
    remux_h264_to_mp4(discovered.raw_h264_path, normalized_path, fps=fps)
    return DiscoveredRealData(
        qv_mp4_path=discovered.qv_mp4_path,
        raw_h264_path=discovered.raw_h264_path,
        normalized_raw_video_path=normalized_path,
        json_dir=discovered.json_dir,
        json_count=discovered.json_count,
    )


def remux_h264_to_mp4(input_path: Path, output_path: Path, fps: float = 30.0) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to remux raw h264 into seekable mp4")
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    command = [
        ffmpeg,
        "-y",
        "-framerate",
        _format_fps(fps),
        "-i",
        str(input_path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "ffmpeg h264 remux failed\n"
            f"command: {' '.join(command)}\n"
            f"stderr: {completed.stderr.strip()}"
        )
    return output_path


def _format_fps(fps: float) -> str:
    return str(int(fps)) if fps.is_integer() else str(fps)
