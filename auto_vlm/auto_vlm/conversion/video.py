"""Video metadata and frame extraction helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from auto_vlm.models.evidence import VideoMetadata


def read_video_metadata(video_path: str | Path) -> VideoMetadata:
    path = Path(video_path)
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(f"video cannot be opened: {path}")
        raw_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_count = raw_frame_count if raw_frame_count > 0 else 0
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return VideoMetadata(
            video_path=path,
            frame_count=frame_count,
            fps=fps,
            width=width,
            height=height,
            decoder_status="ok" if raw_frame_count > 0 else "ok_unknown_frame_count",
        )
    finally:
        capture.release()


def extract_center_frame(video_path: str | Path, frame_index: int, output_path: str | Path) -> Path:
    frame = _read_frame(video_path, frame_index)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), frame):
        raise ValueError(f"failed to write frame image: {output}")
    return output


def extract_context_strip(
    video_path: str | Path,
    sampled_frame: int,
    offsets: tuple[int, ...],
    output_path: str | Path,
) -> Path:
    metadata = read_video_metadata(video_path)
    frames = []
    for offset in offsets:
        requested_frame = max(sampled_frame + offset, 0)
        frame_index = (
            min(requested_frame, metadata.frame_count - 1)
            if metadata.frame_count > 0
            else requested_frame
        )
        frame = _read_frame(video_path, frame_index)
        frames.append(_label_frame(frame, frame_index))

    strip = np.concatenate(frames, axis=1)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), strip):
        raise ValueError(f"failed to write context image: {output}")
    return output


def _read_frame(video_path: str | Path, frame_index: int) -> np.ndarray:
    if frame_index < 0:
        raise ValueError("frame_index cannot be negative")

    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise ValueError(f"video cannot be opened: {video_path}")
        metadata_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if ok and frame is not None and metadata_frame_count > 0:
            return frame
        if metadata_frame_count <= 0:
            capture.release()
            return _read_frame_sequential(video_path, frame_index)
        if not ok or frame is None:
            raise ValueError(f"frame {frame_index} could not be read")
        return frame
    finally:
        capture.release()


def _read_frame_sequential(video_path: str | Path, frame_index: int) -> np.ndarray:
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise ValueError(f"video cannot be opened: {video_path}")
        frame = None
        for _ in range(frame_index + 1):
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(f"frame {frame_index} could not be read sequentially")
        return frame
    finally:
        capture.release()


def _label_frame(frame: np.ndarray, frame_index: int) -> np.ndarray:
    labeled = frame.copy()
    cv2.putText(
        labeled,
        f"f{frame_index}",
        (4, 16),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return labeled
