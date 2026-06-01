from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from auto_vlm.evidence.candidate_packets import write_candidate_evidence_packets
from auto_vlm.evidence.builder import build_frame_evidence_package
from auto_vlm.evidence.feature_packets import write_feature_evidence_packets
from auto_vlm.conversion.video import extract_center_frame, read_video_metadata
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


def test_write_candidate_evidence_packets_for_od_bbox_dup(tmp_path):
    qv_frame = tmp_path / "qv.jpg"
    raw_frame = tmp_path / "raw.jpg"
    image = np.full((120, 160, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(qv_frame), image)
    cv2.imwrite(str(raw_frame), image)
    json_snippet = tmp_path / "frame_00000235.json"
    json_snippet.write_text(
        """
        {
          "avi_objects": {
            "VIS_OBJ_Element": [
              {
                "VIS_OBJ_ID": 171,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 40, "Top_Left_Y": 30,
                  "Bottom_Right_X": 80, "Bottom_Right_Y": 70
                },
                "VIS_OBJ_Physical_State": {"Long_Distance": 31.5, "Lat_Distance": 6.5}
              },
              {
                "VIS_OBJ_ID": 183,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 58, "Top_Left_Y": 34,
                  "Bottom_Right_X": 95, "Bottom_Right_Y": 76
                },
                "VIS_OBJ_Physical_State": {"Long_Distance": 34.2, "Lat_Distance": 8.1}
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    package = build_frame_evidence_package(
        case=EvaluationCase(
            case_id="CASE_002",
            video_path=tmp_path / "sample.mp4",
            sampling_request=SamplingRequest(frame_list=(235,), sampling_frame=None),
            input_source_type="excel",
            project_type="APTIV_FVC",
        ),
        sampled_frame=235,
        video_metadata=read_video_metadata(_video_for_metadata(tmp_path)),
        center_frame_image=qv_frame,
        output_root=tmp_path / "output",
        qv_overlay_frame_image=qv_frame,
        raw_frame_image=raw_frame,
        raw_video_metadata=VideoMetadata(
            video_path=tmp_path / "raw.h264",
            frame_count=300,
            fps=30.0,
            width=160,
            height=120,
        ),
        json_snippet=json_snippet,
        json_summary="objects=11; OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15",
    )

    packets = write_candidate_evidence_packets(package, tmp_path / "output" / "cases" / "CASE_002")

    assert len(packets) == 1
    packet = packets[0]
    assert packet.candidate_id == "OD_BBOX_DUP_171_183"
    assert packet.ics_crop_image and packet.ics_crop_image.exists()
    assert packet.candidate_json_values and packet.candidate_json_values.exists()
    assert packet.bev_crop_status == "unavailable_no_bev_region"
    assert packet.packet_markdown and packet.packet_markdown.exists()
    text = packet.packet_markdown.read_text(encoding="utf-8")
    assert "Raw observation" in text
    assert "BEV overlay observation" in text
    assert "JSON physical values support the BEV overlay observation" in text
    assert "check bev_extent_analysis, not only center distance" in text


def test_candidate_evidence_uses_raw_resolution_for_ics_and_bev_layout(tmp_path):
    qv_frame = tmp_path / "qv_overlay.jpg"
    raw_frame = tmp_path / "raw.jpg"
    overlay = np.zeros((120, 260, 3), dtype=np.uint8)
    overlay[:, :160] = (255, 255, 255)
    overlay[:, 160:] = (64, 64, 64)
    cv2.imwrite(str(qv_frame), overlay)
    cv2.imwrite(str(raw_frame), overlay[:, :160])
    json_snippet = tmp_path / "frame_00000235.json"
    json_snippet.write_text(
        """
        {
          "avi_objects": {
            "VIS_OBJ_Element": [
              {
                "VIS_OBJ_ID": 171,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 40, "Top_Left_Y": 30,
                  "Bottom_Right_X": 80, "Bottom_Right_Y": 70
                }
              },
              {
                "VIS_OBJ_ID": 183,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 58, "Top_Left_Y": 34,
                  "Bottom_Right_X": 95, "Bottom_Right_Y": 76
                }
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    package = build_frame_evidence_package(
        case=EvaluationCase(
            case_id="CASE_002",
            video_path=tmp_path / "sample.mp4",
            sampling_request=SamplingRequest(frame_list=(235,), sampling_frame=None),
            input_source_type="excel",
            project_type="APTIV_FVC",
        ),
        sampled_frame=235,
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
        raw_frame_image=raw_frame,
        raw_video_metadata=VideoMetadata(
            video_path=tmp_path / "raw.h264",
            frame_count=300,
            fps=30.0,
            width=160,
            height=120,
        ),
        json_snippet=json_snippet,
        json_summary="objects=11; OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15",
    )

    packets = write_candidate_evidence_packets(package, tmp_path / "output" / "cases" / "CASE_002")

    packet = packets[0]
    assert packet.ics_crop_status == "available_raw_layout"
    assert packet.bev_crop_status == "available_overlay_right_of_raw"
    assert packet.ics_crop_image and packet.ics_crop_image.exists()
    assert packet.bev_crop_image and packet.bev_crop_image.exists()
    bev = cv2.imread(str(packet.bev_crop_image))
    assert bev.shape[:2] == (120, 100)


def test_candidate_evidence_json_includes_bev_extent_overlap_analysis(tmp_path):
    qv_frame = tmp_path / "qv_overlay.jpg"
    raw_frame = tmp_path / "raw.jpg"
    overlay = np.zeros((120, 260, 3), dtype=np.uint8)
    cv2.imwrite(str(qv_frame), overlay)
    cv2.imwrite(str(raw_frame), overlay[:, :160])
    json_snippet = tmp_path / "frame_00000235.json"
    json_snippet.write_text(
        """
        {
          "avi_objects": {
            "VIS_OBJ_Element": [
              {
                "VIS_OBJ_ID": 172,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 40, "Top_Left_Y": 30,
                  "Bottom_Right_X": 80, "Bottom_Right_Y": 70
                },
                "VIS_OBJ_Physical_State": {
                  "Long_Distance": 44.30,
                  "Lat_Distance": -9.38,
                  "Length": 11.05,
                  "Width": 2.54
                }
              },
              {
                "VIS_OBJ_ID": 182,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 58, "Top_Left_Y": 34,
                  "Bottom_Right_X": 95, "Bottom_Right_Y": 76
                },
                "VIS_OBJ_Physical_State": {
                  "Long_Distance": 53.74,
                  "Lat_Distance": -9.14,
                  "Length": 8.79,
                  "Width": 2.48
                }
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    package = build_frame_evidence_package(
        case=EvaluationCase(
            case_id="CASE_002",
            video_path=tmp_path / "sample.mp4",
            sampling_request=SamplingRequest(frame_list=(235,), sampling_frame=None),
            input_source_type="excel",
            project_type="APTIV_FVC",
        ),
        sampled_frame=235,
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
        raw_frame_image=raw_frame,
        raw_video_metadata=VideoMetadata(
            video_path=tmp_path / "raw.h264",
            frame_count=300,
            fps=30.0,
            width=160,
            height=120,
        ),
        json_snippet=json_snippet,
        json_summary="objects=11; OD_bbox_overlap_candidates=172-182:min_overlap=0.68,iou=0.31",
    )

    packet = write_candidate_evidence_packets(
        package, tmp_path / "output" / "cases" / "CASE_002"
    )[0]
    candidate_json = json.loads(packet.candidate_json_values.read_text(encoding="utf-8"))

    analysis = candidate_json["bev_extent_analysis"]
    assert analysis["status"] == "available"
    assert analysis["extent_overlap_hint"] is True
    assert round(analysis["delta_long"], 2) == 9.44
    assert analysis["longitudinal_extent_overlap"] > 0
    assert analysis["lateral_extent_overlap"] > 0
    hint = candidate_json["candidate_review_hint"]["bev_precheck"]
    assert hint["recommended_decision"] == "review_required_possible_issue"


def test_candidate_evidence_surfaces_bev_clear_precheck_for_separated_dup_candidate(tmp_path):
    qv_frame = tmp_path / "qv_overlay.jpg"
    raw_frame = tmp_path / "raw.jpg"
    overlay = np.zeros((120, 260, 3), dtype=np.uint8)
    overlay[:, :160] = (255, 255, 255)
    overlay[:, 160:] = (64, 64, 64)
    cv2.imwrite(str(qv_frame), overlay)
    cv2.imwrite(str(raw_frame), overlay[:, :160])
    json_snippet = tmp_path / "frame_00000100.json"
    json_snippet.write_text(
        """
        {
          "avi_objects": {
            "VIS_OBJ_Element": [
              {
                "VIS_OBJ_ID": 14,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 40, "Top_Left_Y": 30,
                  "Bottom_Right_X": 90, "Bottom_Right_Y": 80
                },
                "VIS_OBJ_Physical_State": {
                  "Long_Distance": 20.05,
                  "Lat_Distance": -6.07,
                  "Length": 4.0,
                  "Width": 1.8
                }
              },
              {
                "VIS_OBJ_ID": 24,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 55, "Top_Left_Y": 34,
                  "Bottom_Right_X": 100, "Bottom_Right_Y": 82
                },
                "VIS_OBJ_Physical_State": {
                  "Long_Distance": 26.03,
                  "Lat_Distance": -7.82,
                  "Length": 4.0,
                  "Width": 1.6
                }
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    package = build_frame_evidence_package(
        case=EvaluationCase(
            case_id="CASE_001",
            video_path=tmp_path / "sample.mp4",
            sampling_request=SamplingRequest(frame_list=(100,), sampling_frame=None),
            input_source_type="excel",
            project_type="APTIV_FVC",
        ),
        sampled_frame=100,
        video_metadata=read_video_metadata(_video_for_metadata(tmp_path)),
        center_frame_image=qv_frame,
        output_root=tmp_path / "output",
        qv_overlay_frame_image=qv_frame,
        raw_frame_image=raw_frame,
        raw_video_metadata=VideoMetadata(
            video_path=tmp_path / "raw.h264",
            frame_count=300,
            fps=30.0,
            width=160,
            height=120,
        ),
        json_snippet=json_snippet,
        json_summary="objects=13; OD_bbox_overlap_candidates=14-24:min_overlap=0.78,iou=0.27",
    )

    packet = write_candidate_evidence_packets(
        package, tmp_path / "output" / "cases" / "CASE_001"
    )[0]
    candidate_json = json.loads(packet.candidate_json_values.read_text(encoding="utf-8"))

    hint = candidate_json["candidate_review_hint"]["bev_precheck"]
    assert candidate_json["bev_extent_analysis"]["extent_overlap_hint"] is False
    assert hint["recommended_decision"] == "cleared"
    assert "BEV_PRECHECK=cleared" in packet.candidate_review_summary
    assert "delta_long=5.980m" in packet.candidate_review_summary
    assert "BEV separates the objects" in packet.packet_markdown.read_text(encoding="utf-8")


def test_write_candidate_evidence_packets_for_od_bbox_fit_and_rbd_candidates(tmp_path):
    qv_frame = tmp_path / "qv_overlay.jpg"
    raw_frame = tmp_path / "raw.jpg"
    overlay = np.zeros((120, 260, 3), dtype=np.uint8)
    overlay[:, :160] = (255, 255, 255)
    overlay[:, 160:] = (64, 64, 64)
    cv2.imwrite(str(qv_frame), overlay)
    cv2.imwrite(str(raw_frame), overlay[:, :160])
    json_snippet = tmp_path / "frame_00000153.json"
    json_snippet.write_text(
        """
        {
          "avi_objects": {
            "VIS_OBJ_Element": [
              {
                "VIS_OBJ_ID": 60,
                "VIS_OBJ_Image_Coordinates": {
                  "Top_Left_X": 20, "Top_Left_Y": 20,
                  "Bottom_Right_X": 120, "Bottom_Right_Y": 100
                },
                "VIS_OBJ_Physical_State": {
                  "Long_Distance": 18.0,
                  "Lat_Distance": -3.0,
                  "Length": 12.0,
                  "Width": 3.0
                }
              }
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    package = build_frame_evidence_package(
        case=EvaluationCase(
            case_id="CASE_002",
            video_path=tmp_path / "sample.mp4",
            sampling_request=SamplingRequest(frame_list=(153,), sampling_frame=None),
            input_source_type="excel",
            project_type="APTIV_FVC",
        ),
        sampled_frame=153,
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
        raw_frame_image=raw_frame,
        raw_video_metadata=VideoMetadata(
            video_path=tmp_path / "raw.h264",
            frame_count=300,
            fps=30.0,
            width=160,
            height=120,
        ),
        json_snippet=json_snippet,
        json_summary=(
            "objects=8; road_edges=0; "
            "OD_large_bbox_candidates=60:w=0.30,h=0.51,area=0.15; "
            "RBD_low_road_edge_count=0/expected_min=2"
        ),
    )

    packets = write_candidate_evidence_packets(package, tmp_path / "output" / "cases" / "CASE_002")

    by_id = {packet.candidate_id: packet for packet in packets}
    assert set(by_id) == {"OD_BBOX_FIT_LARGE_60", "RBD_LOW_ROAD_EDGE_COUNT_0_OF_2"}
    fit = by_id["OD_BBOX_FIT_LARGE_60"]
    assert fit.ics_crop_image and fit.ics_crop_image.exists()
    assert fit.bev_crop_image and fit.bev_crop_image.exists()
    fit_json = json.loads(fit.candidate_json_values.read_text(encoding="utf-8"))
    assert fit_json["candidate_review_hint"]["primary_json_keys"] == ["OD_large_bbox_candidates"]
    assert "DEF-OD-BBOX-FIT" in fit.packet_markdown.read_text(encoding="utf-8")

    rbd = by_id["RBD_LOW_ROAD_EDGE_COUNT_0_OF_2"]
    assert rbd.ics_crop_image and rbd.ics_crop_image.exists()
    assert rbd.bev_crop_image and rbd.bev_crop_image.exists()
    rbd_text = rbd.packet_markdown.read_text(encoding="utf-8")
    assert "DEF-LD-RBD-FN" in rbd_text
    assert "RBD_low_road_edge_count" in rbd_text


def test_write_feature_evidence_packets_cover_all_active_features(tmp_path):
    video_path = tmp_path / "sample.mp4"
    _write_tiny_video(video_path)
    metadata = read_video_metadata(video_path)
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
        video_metadata=metadata,
        center_frame_image=qv_frame,
        output_root=tmp_path / "output",
        qv_overlay_frame_image=qv_frame,
        json_summary="objects=3; lanes=2; road_edges=1; signs=1; lights=1",
    )

    packets = write_feature_evidence_packets(package, tmp_path / "output" / "cases" / "CASE_001")

    assert [packet.feature for packet in packets] == ["OD", "LD", "RBD", "TS", "TL"]
    assert all(packet.packet_markdown and packet.packet_markdown.exists() for packet in packets)
    od_text = packets[0].packet_markdown.read_text(encoding="utf-8")
    assert "This packet is for a full feature sweep" in od_text
    assert "Issue Evidence Strategy" in od_text
    assert "Issue Types To Sweep" in od_text
    assert "DEF-OD-BBOX-DUP" in od_text
    assert "DEF-OD-HEADING | primary_discovery: BEV/VCS geometry and JSON spatial values" in od_text
    assert "Do not require the issue to be obvious in ICS before checking BEV/VCS" in od_text
    assert "Do not judge only machine candidates" in od_text


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


def _video_for_metadata(tmp_path: Path) -> Path:
    video_path = tmp_path / "metadata.mp4"
    _write_tiny_video(video_path)
    return video_path
