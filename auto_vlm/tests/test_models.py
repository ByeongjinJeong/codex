from __future__ import annotations

from pathlib import Path

import pytest

from auto_vlm.models.cases import EvaluationCase, SamplingMode, SamplingRequest
from auto_vlm.models.evidence import (
    EvidenceIntegrity,
    FrameEvidencePackage,
    JsonFrameMatchStatus,
    JsonParseStatus,
    VideoMetadata,
)
from auto_vlm.models.results import Judgment, PackageReviewResult
from auto_vlm.utils.errors import ToolError


def test_sampling_request_defaults_to_full_video_uniform():
    request = SamplingRequest()

    assert request.sampling_frame == 50
    assert request.mode == SamplingMode.FULL_VIDEO_INTERVAL


def test_sampling_request_frame_list_wins_and_deduplicates():
    request = SamplingRequest(frame_list=(100, 100, 200), start_frame=1, end_frame=300, sampling_frame=None)

    assert request.frame_list == (100, 200)
    assert request.mode == SamplingMode.EXPLICIT_FRAMES


def test_sampling_request_rejects_invalid_values():
    with pytest.raises(ValueError, match="sampling_frame"):
        SamplingRequest(sampling_frame=0)

    with pytest.raises(ValueError, match="negative"):
        SamplingRequest(frame_list=(-1,), sampling_frame=None)

    with pytest.raises(ValueError, match="greater than end_frame"):
        SamplingRequest(start_frame=10, end_frame=5)


def test_evaluation_case_defaults_focus_feature_to_all():
    case = EvaluationCase(
        case_id=" CASE_001 ",
        video_path=Path("sample.mp4"),
        raw_video_path=Path("sample.h264"),
        sampling_request=SamplingRequest(),
        input_source_type="excel",
        input_source_path=Path("cases.xlsx"),
        focus_feature="",
        external_metadata={"unknown_column": "value"},
    )

    assert case.case_id == "CASE_001"
    assert case.focus_feature == "ALL"
    assert case.source_case_metadata()["input_source_type"] == "excel"
    assert case.qv_video_path == Path("sample.mp4")
    assert case.raw_video_path == Path("sample.h264")
    assert case.source_case_metadata()["external_metadata"]["unknown_column"] == "value"


def test_evaluation_case_accepts_multiple_focus_features():
    case = EvaluationCase(
        case_id="CASE_001",
        video_path=Path("sample.mp4"),
        sampling_request=SamplingRequest(frame_list=(1,), sampling_frame=None),
        focus_feature="OD,RBD",
    )

    assert case.focus_feature == "OD,RBD"


def test_evaluation_case_requires_case_id():
    with pytest.raises(ValueError, match="case_id is required"):
        EvaluationCase(case_id="", video_path=Path("sample.mp4"), sampling_request=SamplingRequest())


def test_evidence_integrity_defaults_support_missing_json():
    integrity = EvidenceIntegrity()

    assert integrity.json_available is False
    assert integrity.json_frame_match_status == JsonFrameMatchStatus.MISSING_JSON_DIR
    assert integrity.json_parse_status == JsonParseStatus.MISSING
    assert integrity.as_dict()["raw_video_available"] is False
    assert integrity.as_dict()["visualizer_module_visibility_unknown"] is True


def test_frame_evidence_package_has_required_fields_and_package_id_helper():
    video_metadata = VideoMetadata(
        video_path=Path("sample.mp4"),
        frame_count=300,
        fps=30.0,
        width=1920,
        height=1080,
    )
    integrity = EvidenceIntegrity(
        json_available=True,
        json_frame_match_status=JsonFrameMatchStatus.EXACT,
        json_parse_status=JsonParseStatus.OK,
    )
    package = FrameEvidencePackage(
        package_id=FrameEvidencePackage.make_package_id("CASE_001", 100),
        case_id="CASE_001",
        sampled_frame=100,
        timestamp_sec=100 / 30.0,
        center_frame_image=Path("output/cases/CASE_001/frames/frame_00000100.jpg"),
        video_metadata=video_metadata,
        raw_frame_image=Path("output/cases/CASE_001/raw_frames/frame_00000100.jpg"),
        raw_video_metadata=video_metadata,
        qv_overlay_frame_image=Path("output/cases/CASE_001/qv_frames/frame_00000100.jpg"),
        qv_video_metadata=video_metadata,
        project_type="APTIV_FVC",
        source_case_metadata={"case_id": "CASE_001"},
        evidence_integrity=integrity,
        sampling_mode="explicit_frames",
    )

    assert package.package_id == "CASE_001__frame_00000100"
    assert package.video_metadata.as_dict()["fps"] == 30.0
    assert package.raw_frame_image is not None
    assert package.qv_overlay_frame_image is not None
    assert package.evidence_integrity.json_available is True


def test_frame_evidence_package_rejects_invalid_frame():
    video_metadata = VideoMetadata(
        video_path=Path("sample.mp4"),
        frame_count=300,
        fps=30.0,
        width=1920,
        height=1080,
    )

    with pytest.raises(ValueError, match="sampled_frame"):
        FrameEvidencePackage(
            package_id="bad",
            case_id="CASE_001",
            sampled_frame=-1,
            timestamp_sec=0.0,
            center_frame_image=Path("frame.jpg"),
            video_metadata=video_metadata,
            project_type=None,
            source_case_metadata={},
            evidence_integrity=EvidenceIntegrity(),
        )


def test_default_no_vlm_result_is_conservative():
    result = PackageReviewResult()

    assert result.judgment == Judgment.NEEDS_MORE_EVIDENCE
    assert result.need_human_review is True
    assert result.summary == ""


def test_tool_error_message_shape():
    error = ToolError(
        code="missing_video",
        problem="video path does not exist",
        location="row 2 video_path",
        cause="file not found",
        fix="check the video_path cell",
        case_id="CASE_001",
    )

    message = error.as_message()

    assert "problem: video path does not exist" in message
    assert "fix: check the video_path cell" in message
