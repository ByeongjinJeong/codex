from __future__ import annotations

from pathlib import Path

import pytest

from auto_vlm.vlm.contract import build_vlm_prompt_payload, write_vlm_review_packet
from auto_vlm.vlm.review_tasks import build_review_tasks
from auto_vlm.models.evidence import CandidateEvidencePacket, EvidenceIntegrity, FeatureEvidencePacket, FrameEvidencePackage, VideoMetadata
from auto_vlm.models.results import Confidence, Judgment, ReviewPriority, SuspiciousType
from auto_vlm.models.vlm import Feature, VlmEvaluationResult


def _package(focus_feature: str = "ALL") -> FrameEvidencePackage:
    return FrameEvidencePackage(
        package_id="CASE_001__frame_00000100",
        case_id="CASE_001",
        sampled_frame=100,
        timestamp_sec=3.333,
        center_frame_image=Path("frame.jpg"),
        video_metadata=VideoMetadata(
            video_path=Path("sample.mp4"),
            frame_count=300,
            fps=30.0,
            width=1920,
            height=1080,
        ),
        raw_frame_image=Path("raw_frame.jpg"),
        qv_overlay_frame_image=Path("qv_frame.jpg"),
        raw_video_metadata=VideoMetadata(
            video_path=Path("sample.h264"),
            frame_count=300,
            fps=30.0,
            width=1920,
            height=1080,
        ),
        project_type="APTIV_FVC",
        source_case_metadata={"case_id": "CASE_001"},
        evidence_integrity=EvidenceIntegrity(),
        focus_feature=focus_feature,
        json_summary="objects=3; lanes=4",
    )


def _package_with_json_summary(json_summary: str, focus_feature: str = "ALL") -> FrameEvidencePackage:
    package = _package(focus_feature=focus_feature)
    return FrameEvidencePackage(
        package_id=package.package_id,
        case_id=package.case_id,
        sampled_frame=package.sampled_frame,
        timestamp_sec=package.timestamp_sec,
        center_frame_image=package.center_frame_image,
        video_metadata=package.video_metadata,
        raw_frame_image=package.raw_frame_image,
        qv_overlay_frame_image=package.qv_overlay_frame_image,
        raw_video_metadata=package.raw_video_metadata,
        project_type=package.project_type,
        source_case_metadata=package.source_case_metadata,
        evidence_integrity=package.evidence_integrity,
        focus_feature=focus_feature,
        json_summary=json_summary,
    )


def _package_with_candidate_packet() -> FrameEvidencePackage:
    package = _package_with_json_summary(
        "objects=11; OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15"
    )
    return FrameEvidencePackage(
        package_id=package.package_id,
        case_id=package.case_id,
        sampled_frame=package.sampled_frame,
        timestamp_sec=package.timestamp_sec,
        center_frame_image=package.center_frame_image,
        video_metadata=package.video_metadata,
        raw_frame_image=package.raw_frame_image,
        qv_overlay_frame_image=package.qv_overlay_frame_image,
        raw_video_metadata=package.raw_video_metadata,
        project_type=package.project_type,
        source_case_metadata=package.source_case_metadata,
        evidence_integrity=package.evidence_integrity,
        focus_feature=package.focus_feature,
        json_summary=package.json_summary,
        candidate_evidence_packets=(
            CandidateEvidencePacket(
                candidate_id="OD_BBOX_DUP_171_183",
                package_id=package.package_id,
                feature="OD",
                issue_type="DEF-OD-BBOX-DUP",
                object_ids=("171", "183"),
                source="OD_bbox_overlap_candidates",
                raw_frame_image=Path("raw_frame.jpg"),
                qv_overlay_frame_image=Path("qv_frame.jpg"),
                ics_crop_image=Path("OD_BBOX_DUP_171_183__ics.jpg"),
                ics_crop_status="available",
                candidate_json_values=Path("OD_BBOX_DUP_171_183__json.json"),
                packet_markdown=Path("OD_BBOX_DUP_171_183.md"),
                json_summary=package.json_summary or "",
                candidate_review_summary=(
                    "BEV_PRECHECK=cleared; delta_long=5.000m; delta_lat=2.000m; "
                    "BEV separates the objects"
                ),
            ),
        ),
        feature_evidence_packets=(
            FeatureEvidencePacket(
                package_id=package.package_id,
                feature="OD",
                raw_frame_image=Path("raw_frame.jpg"),
                qv_overlay_frame_image=Path("qv_frame.jpg"),
                json_snippet=Path("frame.json"),
                json_summary=package.json_summary or "",
                evaluated_issue_types=("DEF-OD-BBOX-DUP", "DEF-OD-BBOX-FIT"),
                candidate_packet_paths=(Path("OD_BBOX_DUP_171_183.md"),),
                packet_markdown=Path("OD.md"),
            ),
        ),
    )


def test_vlm_result_validates_enums_and_required_text():
    result = VlmEvaluationResult.from_mapping(
        {
            "judgment": "needs_more_evidence",
            "confidence": "low",
            "feature": "ALL",
            "suspicious_type": "unclear",
            "review_priority": "medium",
            "summary": "추가 확인 필요",
            "observed_evidence": "center/context image exists",
            "inference": "no final issue claim",
            "uncertainty": "VLM contract test only",
        }
    )

    assert result.judgment == Judgment.NEEDS_MORE_EVIDENCE
    assert result.confidence == Confidence.LOW
    assert result.feature == Feature.ALL
    assert result.suspicious_type == SuspiciousType.UNCLEAR
    assert result.review_priority == ReviewPriority.MEDIUM


def test_vlm_result_rejects_invalid_enum():
    with pytest.raises(ValueError):
        VlmEvaluationResult.from_mapping(
            {
                "judgment": "confirmed_bug",
                "confidence": "low",
                "feature": "ALL",
                "suspicious_type": "unclear",
                "review_priority": "medium",
                "summary": "bad",
                "observed_evidence": "evidence",
                "inference": "inference",
                "uncertainty": "uncertainty",
            }
        )


def test_vlm_result_requires_observed_inference_uncertainty():
    with pytest.raises(ValueError, match="observed_evidence"):
        VlmEvaluationResult(
            judgment=Judgment.NEEDS_MORE_EVIDENCE,
            confidence=Confidence.LOW,
            feature=Feature.ALL,
            suspicious_type=SuspiciousType.UNCLEAR,
            review_priority=ReviewPriority.MEDIUM,
            summary="summary",
            observed_evidence="",
            inference="inference",
            uncertainty="uncertainty",
        )


def test_prompt_payload_consumes_frame_evidence_package_only():
    payload = build_vlm_prompt_payload(_package())

    assert payload["package_id"] == "CASE_001__frame_00000100"
    assert payload["raw_frame_image"] == "raw_frame.jpg"
    assert payload["qv_overlay_frame_image"] == "qv_frame.jpg"
    assert payload["json_summary"] == "objects=3; lanes=4"
    assert "invent JSON values" in payload["instructions"]["must_not"][1]
    assert any("every issue type" in item for item in payload["instructions"]["compare_order"])
    assert any("BEV/world-space" in item and "JSON physical values" in item for item in payload["instructions"]["compare_order"])
    assert any("coarse symptoms" in item for item in payload["instructions"]["must_not"])
    assert any("ICS/image overlay looks correct" in item for item in payload["instructions"]["must_not"])
    assert any("ICS/image overlay" in item for item in payload["adas_review_workflow"])
    assert any("BEV/world-space" in item for item in payload["adas_review_workflow"])
    assert any("ICS/image overlay looks correct" in item for item in payload["adas_must_not"])
    assert [context["feature"] for context in payload["feature_review_contexts"]] == [
        "OD",
        "LD",
        "RBD",
        "TS",
        "TL",
    ]


def test_prompt_payload_includes_focus_feature_review_context():
    payload = build_vlm_prompt_payload(_package(focus_feature="OD"))
    contexts = payload["feature_review_contexts"]

    assert len(contexts) == 1
    assert contexts[0]["feature"] == "OD"
    assert "docs/references/qualification_visualizer_output_info.md" in contexts[0]["reference_sources"]
    assert "docs/references/regression_issue_types/common.md" in contexts[0]["reference_sources"]
    assert "docs/references/regression_issue_types/od.md" in contexts[0]["reference_sources"]
    assert contexts[0]["qv_json_interpretation"]
    assert contexts[0]["issue_type_guidance"]
    assert contexts[0]["inspection_checklist"]


def test_prompt_payload_rejects_raw_case_like_input():
    with pytest.raises(TypeError, match="FrameEvidencePackage"):
        build_vlm_prompt_payload({"case_id": "CASE_001"})  # type: ignore[arg-type]


def test_write_vlm_review_packet_creates_llm_ready_markdown(tmp_path):
    packet = write_vlm_review_packet(_package(), tmp_path / "vlm_packets")

    text = packet.read_text(encoding="utf-8")
    assert "VLM Review Packet: CASE_001__frame_00000100" in text
    assert "raw_frame_image: raw_frame.jpg" in text
    assert "qv_overlay_frame_image: qv_frame.jpg" in text
    assert "## ADAS Vision Review Workflow" in text
    assert "## Feature Review Context" in text
    assert "### OD" in text
    assert "docs/references/regression_issue_types/od.md" in text
    assert "evaluate every issue type listed in each feature review context" in text
    assert "Do not stop when ICS looks correct" in text
    assert "BEV/JSON can reveal physical-value issues" in text
    assert "prefer OD heading angle or OD BBOX duplication" in text
    assert "evaluated_issue_types: [DEF-* ids evaluated in this review mode]" in text
    assert "triggered_issue_types: [evaluated DEF-* ids judged present, or []]" in text
    assert "observed_evidence: must explicitly cite raw frame evidence, QV overlay evidence, and JSON summary/snippet evidence" in text


def test_write_vlm_review_packet_lifts_json_issue_hints_into_required_cues(tmp_path):
    packet = write_vlm_review_packet(
        _package_with_json_summary(
            "objects=11; lanes=2; road_edges=0; "
            "OD_heading_samples=171:-3.13/o6; "
            "OD_bbox_overlap_candidates=171-183:min_overlap=0.79,iou=0.15; "
            "OD_large_bbox_candidates=60:w=0.30,h=0.51,area=0.16"
        ),
        tmp_path / "vlm_packets",
    )

    text = packet.read_text(encoding="utf-8")
    assert "## Machine-Detected Review Cues" in text
    assert "DEF-OD-HEADING" in text
    assert "Compare the visible travel direction in the raw frame with the BEV/VCS object orientation" in text
    assert "trigger DEF-OD-HEADING even when the bbox-fit issue is also present" in text
    assert "DEF-OD-BBOX-DUP" in text
    assert "ICS/image overlap is only a review cue, never sufficient evidence for duplication" in text
    assert "BEV/VCS separates them, clear that pair" in text
    assert "DEF-OD-BBOX-FIT" in text
    assert "Large image coverage is only a review cue, never sufficient evidence for a bbox-fit issue" in text
    assert "near-field large vehicle/object" in text
    assert "also evaluate and trigger DEF-OD-HEADING instead of reporting only BBOX-FIT" in text
    assert "DEF-LD-RBD-FN" in text
    assert "Treat machine-detected review cues as required checks" in text


def test_write_vlm_review_packet_is_short_index_when_candidate_packets_exist(tmp_path):
    packet = write_vlm_review_packet(_package_with_candidate_packet(), tmp_path / "vlm_packets")

    text = packet.read_text(encoding="utf-8")
    assert "VLM Review Index" in text
    assert "OD.md" in text
    assert "OD_BBOX_DUP_171_183.md" in text
    assert "OD_BBOX_DUP_171_183__ics.jpg" in text
    assert "BEV_PRECHECK=cleared" in text
    assert "Do not apply one fixed plane order to every issue" in text
    assert "BEV/VCS before ICS confirmation" in text
    assert "JSON is the SW output being reviewed" in text
    assert "## Feature Review Context" not in text
    assert "docs/references/regression_issue_types/od.md" not in text
    assert len(text.splitlines()) < 110


def test_write_vlm_review_packet_lifts_low_road_edge_count_into_rbd_cue(tmp_path):
    packet = write_vlm_review_packet(
        _package_with_json_summary(
            "objects=11; lanes=2; road_edges=1; "
            "RBD_low_road_edge_count=1/expected_min=2"
        ),
        tmp_path / "vlm_packets",
    )

    text = packet.read_text(encoding="utf-8")
    assert "RBD_low_road_edge_count is present" in text
    assert "DEF-LD-RBD-FN" in text
    assert "DEF-LD-RBD-RANGE" in text
    assert "partial miss" in text


def test_review_tasks_include_large_bbox_candidate_obligation():
    tasks = build_review_tasks(
        [
            _package_with_json_summary(
                "objects=8; lanes=2; "
                "OD_large_bbox_candidates=60:w=0.30,h=0.51,area=0.15"
            )
        ]
    )

    candidate = tasks["packages"][0]["candidate_tasks"][0]
    assert candidate["task_id"] == "OD_BBOX_FIT_LARGE_60"
    assert candidate["feature"] == "OD"
    assert candidate["issue_type"] == "DEF-OD-BBOX-FIT"
    assert candidate["object_ids"] == ["60"]
    assert candidate["source"] == "OD_large_bbox_candidates"
    assert "DEF-OD-BBOX-FIT" in candidate["decision_rule"]
    assert "OD_large_bbox_candidates" in candidate["decision_rule"]
    assert candidate["evidence_strategy"]["issue_type"] == "DEF-OD-BBOX-FIT"
    assert "raw object shape" in candidate["evidence_strategy"]["primary_discovery"]


def test_review_tasks_include_low_road_edge_candidate_obligation():
    tasks = build_review_tasks(
        [
            _package_with_json_summary(
                "objects=8; lanes=2; road_edges=1; "
                "RBD_low_road_edge_count=1/expected_min=2"
            )
        ]
    )

    candidate = tasks["packages"][0]["candidate_tasks"][0]
    assert candidate["task_id"] == "RBD_LOW_ROAD_EDGE_COUNT_1_OF_2"
    assert candidate["feature"] == "RBD"
    assert candidate["issue_type"] == "DEF-LD-RBD-FN"
    assert candidate["object_ids"] == []
    assert candidate["source"] == "RBD_low_road_edge_count"
    assert "DEF-LD-RBD-FN" in candidate["decision_rule"]
    assert "RBD_low_road_edge_count" in candidate["decision_rule"]


def test_review_tasks_include_issue_specific_evidence_strategy_for_bev_first_items():
    tasks = build_review_tasks([_package_with_json_summary("objects=8; lanes=2")])

    od_task = next(
        item
        for item in tasks["packages"][0]["feature_tasks"]
        if item["feature"] == "OD"
    )
    strategies = {
        item["issue_type"]: item
        for item in od_task["issue_evidence_strategy"]
    }

    assert "DEF-OD-HEADING" in strategies
    assert strategies["DEF-OD-HEADING"]["review_order"] == ["raw_context", "bev_vcs", "json", "ics"]
    assert "BEV/VCS geometry" in strategies["DEF-OD-HEADING"]["primary_discovery"]
