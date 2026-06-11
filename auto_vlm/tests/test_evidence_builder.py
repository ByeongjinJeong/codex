from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from auto_vlm.conversion.video import extract_center_frame, read_video_metadata
from auto_vlm.evidence.builder import build_frame_evidence_package
from auto_vlm.evidence.feature_packets import write_feature_evidence_packets
from auto_vlm.models.cases import EvaluationCase, SamplingRequest
from auto_vlm.models.evidence import VideoMetadata


def _write_tiny_video(path: Path, frame_count: int = 8, size: tuple[int, int] = (32, 24)) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 4.0, size)
    try:
        for index in range(frame_count):
            frame = np.full((size[1], size[0], 3), index * 20, dtype=np.uint8)
            writer.write(frame)
    finally:
        writer.release()


def test_video_metadata_and_frame_extraction(tmp_path):
    video_path = tmp_path / "sample.mp4"
    _write_tiny_video(video_path)

    metadata = read_video_metadata(video_path)
    center = extract_center_frame(video_path, 3, tmp_path / "frames" / "frame_00000003.jpg")

    assert metadata.frame_count == 8
    assert metadata.fps == 4.0
    assert center.exists()


def test_build_frame_evidence_package_without_json(tmp_path):
    video_path = tmp_path / "sample.mp4"
    _write_tiny_video(video_path)
    metadata = read_video_metadata(video_path)
    center = extract_center_frame(video_path, 2, tmp_path / "output/cases/CASE_001/frames/frame_00000002.jpg")
    case = EvaluationCase(
        case_id="CASE_001",
        video_path=video_path,
        sampling_request=SamplingRequest(frame_list=(2,), sampling_frame=None),
        input_source_type="excel",
        project_type="APTIV_FVC",
    )

    package = build_frame_evidence_package(
        case=case,
        sampled_frame=2,
        video_metadata=metadata,
        center_frame_image=center,
        output_root=tmp_path / "output",
        sampling_mode=case.sampling_request.mode.value,
    )

    assert package.package_id == "CASE_001__frame_00000002"
    assert package.timestamp_sec == 0.5
    assert package.evidence_integrity.json_available is False
    assert package.center_frame_image.exists()
    assert package.context_image is None


def test_write_feature_evidence_packets_cover_all_active_features(tmp_path):
    video_path = tmp_path / "sample.mp4"
    _write_tiny_video(video_path)
    qv_frame = extract_center_frame(video_path, 2, tmp_path / "qv.jpg")
    case = EvaluationCase(
        case_id="CASE_001",
        video_path=video_path,
        sampling_request=SamplingRequest(frame_list=(2,), sampling_frame=None),
        input_source_type="excel",
        project_type="APTIV_FVC",
    )
    package = build_frame_evidence_package(
        case=case,
        sampled_frame=2,
        video_metadata=VideoMetadata(
            video_path=tmp_path / "qv.mp4",
            frame_count=300,
            fps=30.0,
            width=260,
            height=120,
        ),
        center_frame_image=qv_frame,
        output_root=tmp_path / "output",
        qv_overlay_frame_image=qv_frame,
        raw_frame_image=qv_frame,
        raw_video_metadata=VideoMetadata(
            video_path=tmp_path / "raw.h264",
            frame_count=300,
            fps=30.0,
            width=160,
            height=120,
        ),
        json_summary="objects=3; lanes=2; road_edges=1; signs=1; lights=1",
        evaluation_scope={
            "features": {
                "OD": {
                    "rules": {"vehicle_max_long_distance_m": 100.0, "vru_max_long_distance_m": 70.0},
                    "summary": {"in_scope": 1, "out_of_scope": 1, "scope_uncertain": 0},
                    "objects": [
                        {
                            "object_id": "1",
                            "class": "car",
                            "category": "vehicle",
                            "long_distance_m": 82.0,
                            "scope": "in_scope",
                            "reason": "vehicle within 100m",
                        }
                    ],
                }
            }
        },
    )

    packets = write_feature_evidence_packets(package, tmp_path / "output" / "cases" / "CASE_001")

    assert [packet.feature for packet in packets] == ["OD", "LD", "RBD", "TS", "TL"]
    assert all(packet.packet_markdown and packet.packet_markdown.exists() for packet in packets)
    od_text = packets[0].packet_markdown.read_text(encoding="utf-8")
    assert "This packet is for a full feature sweep" in od_text
    assert "Issue Evidence Strategy" in od_text
    assert "Issue Types To Sweep" in od_text
    assert "DEF-OD-BBOX-DUP" in od_text
    assert "DEF-OD-HEADING" in od_text
    assert "primary_discovery" in od_text
    assert "## Evaluation Scope" in od_text
    assert "vehicle_max_long_distance_m" in od_text
    assert "candidate" not in od_text.lower()


def test_write_feature_evidence_packets_cover_all_active_features_even_when_focus_is_od(tmp_path):
    video_path = tmp_path / "sample.mp4"
    _write_tiny_video(video_path)
    qv_frame = extract_center_frame(video_path, 2, tmp_path / "qv.jpg")
    package = build_frame_evidence_package(
        case=EvaluationCase(
            case_id="CASE_001",
            video_path=video_path,
            sampling_request=SamplingRequest(frame_list=(2,), sampling_frame=None),
            input_source_type="excel",
            project_type="APTIV_FVC",
            focus_feature="OD",
        ),
        sampled_frame=2,
        video_metadata=VideoMetadata(
            video_path=tmp_path / "qv.mp4",
            frame_count=300,
            fps=30.0,
            width=260,
            height=120,
        ),
        center_frame_image=qv_frame,
        output_root=tmp_path / "output",
        qv_overlay_frame_image=qv_frame,
        raw_frame_image=qv_frame,
        raw_video_metadata=VideoMetadata(
            video_path=tmp_path / "raw.h264",
            frame_count=300,
            fps=30.0,
            width=160,
            height=120,
        ),
        json_summary="objects=3; lanes=2; road_edges=1; signs=1; lights=1",
    )

    packets = write_feature_evidence_packets(package, tmp_path / "output" / "cases" / "CASE_001")

    assert [packet.feature for packet in packets] == ["OD", "LD", "RBD", "TS", "TL"]
