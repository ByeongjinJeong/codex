from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from openpyxl import load_workbook

from auto_vlm.evidence.builder import build_frame_evidence_package
from auto_vlm.models.cases import EvaluationCase, SamplingRequest
from auto_vlm.models.evidence import CandidateEvidencePacket, FeatureEvidencePacket, VideoMetadata
from auto_vlm.models.results import (
    CandidateAdjudication,
    Confidence,
    FeatureReviewResult,
    Judgment,
    PackageReviewResult,
    ReviewPriority,
    SuspiciousType,
    FrameTestResult,
)
from auto_vlm.reports.excel_report import write_result_xlsx
from auto_vlm.reports.html_report import write_summary_html
from auto_vlm.utils.errors import ToolError


def _package(tmp_path: Path):
    center = tmp_path / "output/cases/CASE_001/frames/frame_00000100.jpg"
    raw = tmp_path / "output/cases/CASE_001/raw_frames/frame_00000100.jpg"
    qv = tmp_path / "output/cases/CASE_001/qv_frames/frame_00000100.jpg"
    json_snippet = tmp_path / "output/cases/CASE_001/json_snippets/frame_00000100.json"
    for path in (center, raw, qv, json_snippet):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake")
    case = EvaluationCase(
        case_id="CASE_001",
        video_path=Path("sample.mp4"),
        sampling_request=SamplingRequest(frame_list=(100,), sampling_frame=None),
        input_source_type="excel",
        input_source_path=Path("cases.xlsx"),
        json_dir=Path("json"),
        project_type="APTIV_FVC",
    )
    metadata = VideoMetadata(
        video_path=Path("sample.mp4"),
        frame_count=300,
        fps=30.0,
        width=1920,
        height=1080,
    )
    return build_frame_evidence_package(
        case=case,
        sampled_frame=100,
        video_metadata=metadata,
        center_frame_image=center,
        output_root=tmp_path / "output",
        qv_overlay_frame_image=qv,
        raw_frame_image=raw,
        json_snippet=json_snippet,
        json_summary="objects=2; lanes=1",
        sampling_mode=case.sampling_request.mode.value,
    )


def test_write_result_xlsx_links_evidence(tmp_path):
    package = _package(tmp_path)
    output_path = write_result_xlsx(tmp_path / "output/result.xlsx", [package])

    workbook = load_workbook(output_path)
    assert workbook.sheetnames == ["results", "feature_results"]
    sheet = workbook["results"]
    headers = [cell.value for cell in sheet[1]]
    row = {header: sheet.cell(row=2, column=index + 1).value for index, header in enumerate(headers)}

    assert row["case_id"] == "CASE_001"
    assert row["frame_result"] == "needs_review"
    assert row["judgment"] == "needs_more_evidence"
    assert row["review_source"] == "unknown"
    assert row["evidence_image"].endswith("frame_00000100.jpg")
    assert row["context_image"] in (None, "")
    assert row["qv_overlay_frame_image"].endswith("frame_00000100.jpg")
    assert sheet.cell(row=2, column=headers.index("summary") + 1).alignment.wrap_text is True
    assert sheet.column_dimensions[sheet.cell(row=1, column=headers.index("summary") + 1).column_letter].width >= 50


def test_write_result_xlsx_includes_feature_result_evidence_sheet(tmp_path):
    package = _package(tmp_path)
    result = PackageReviewResult(
        feature_results=(
            FeatureReviewResult(
                feature="OD",
                result=FrameTestResult.FAIL,
                confidence=Confidence.HIGH,
                evaluated_issue_types=("ISSUE_OD_GEOMETRY",),
                triggered_issue_types=("ISSUE_OD_GEOMETRY",),
                summary="OD bbox geometry is wrong",
                observed_evidence="raw frame bus, QV overlay oversized box, JSON object id 60",
                inference="OD fails this frame",
                uncertainty="single-frame review",
            ),
        )
    )

    output_path = write_result_xlsx(
        tmp_path / "output/result.xlsx",
        [package],
        results={package.package_id: result},
    )

    sheet = load_workbook(output_path)["feature_results"]
    headers = [cell.value for cell in sheet[1]]
    row = {header: sheet.cell(row=2, column=index + 1).value for index, header in enumerate(headers)}

    assert row["package_id"] == package.package_id
    assert row["feature"] == "OD"
    assert row["result"] == "fail"
    assert row["triggered_issue_types"] == "ISSUE_OD_GEOMETRY"
    assert "CASE_001 frame 100 OD 관찰 증거" in row["observed_evidence"]
    assert "raw_frame_image=" in row["observed_evidence"]
    assert "qv_overlay_frame_image=" in row["observed_evidence"]
    assert "json_snippet=" in row["observed_evidence"]
    assert "CASE_001 frame 100 OD 판단" in row["inference"]
    assert "fail로 판정합니다" in row["inference"]


def test_write_result_xlsx_keeps_candidate_details_out_of_final_sheet(tmp_path):
    package = _package(tmp_path)
    result = PackageReviewResult(
        feature_results=(
            FeatureReviewResult(
                feature="OD",
                result=FrameTestResult.FAIL,
                confidence=Confidence.HIGH,
                evaluated_issue_types=("ISSUE_OD_DUPLICATE",),
                triggered_issue_types=("ISSUE_OD_DUPLICATE",),
                summary="전방 원거리 차량 영역에서 172-182 OD BBOX 중복 검출 이슈",
                candidate_adjudications=(
                    CandidateAdjudication(
                        candidate_id="CANDIDATE_CLEARED",
                        feature="OD",
                        issue_type="ISSUE_OD_DUPLICATE",
                        object_ids=("171", "183"),
                        result="cleared",
                        checked_planes=("raw", "ics", "bev_vcs", "json"),
                        summary="171-183 is cleared by BEV/VCS separation.",
                    ),
                    CandidateAdjudication(
                        candidate_id="CANDIDATE_ISSUE",
                        feature="OD",
                        issue_type="ISSUE_OD_DUPLICATE",
                        object_ids=("172", "182"),
                        result="issue",
                        checked_planes=("raw", "ics", "bev_vcs", "json"),
                        summary="172-182 is confirmed as OD bbox duplication.",
                    ),
                ),
            ),
        )
    )

    output_path = write_result_xlsx(
        tmp_path / "output/result.xlsx",
        [package],
        results={package.package_id: result},
    )

    sheet = load_workbook(output_path)["feature_results"]
    headers = [cell.value for cell in sheet[1]]
    row = {header: sheet.cell(row=2, column=index + 1).value for index, header in enumerate(headers)}

    assert "candidate_adjudications" not in headers
    assert "candidate_evidence_artifacts" not in headers
    assert row["summary"] == "전방 원거리 차량 영역에서 172-182 OD BBOX 중복 검출 이슈"


def test_reports_expose_feature_crop_artifacts_without_candidate_details(tmp_path):
    package = _package(tmp_path)
    feature_ics = tmp_path / "output/cases/CASE_001/feature_evidence/CASE_001__frame_00000100/OD__ics.jpg"
    feature_bev = tmp_path / "output/cases/CASE_001/feature_evidence/CASE_001__frame_00000100/OD__bev.jpg"
    candidate_ics = tmp_path / "output/cases/CASE_001/candidate_evidence/CASE_001__frame_00000100/CANDIDATE_ISSUE__ics.jpg"
    candidate_bev = tmp_path / "output/cases/CASE_001/candidate_evidence/CASE_001__frame_00000100/CANDIDATE_ISSUE__bev.jpg"
    candidate_json = tmp_path / "output/cases/CASE_001/candidate_evidence/CASE_001__frame_00000100/CANDIDATE_ISSUE__json.json"
    for path in (feature_ics, feature_bev, candidate_ics, candidate_bev, candidate_json):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake")
    package = replace(
        package,
        feature_evidence_packets=(
            FeatureEvidencePacket(
                package_id=package.package_id,
                feature="OD",
                ics_crop_image=feature_ics,
                bev_crop_image=feature_bev,
            ),
        ),
        candidate_evidence_packets=(
            CandidateEvidencePacket(
                candidate_id="CANDIDATE_ISSUE",
                package_id=package.package_id,
                feature="OD",
                issue_type="ISSUE_OD_DUPLICATE",
                object_ids=("172", "182"),
                source="OD_bbox_overlap_candidates",
                ics_crop_image=candidate_ics,
                bev_crop_image=candidate_bev,
                candidate_json_values=candidate_json,
            ),
        ),
    )
    result = PackageReviewResult(
        feature_results=(
            FeatureReviewResult(
                feature="OD",
                result=FrameTestResult.FAIL,
                confidence=Confidence.HIGH,
                evaluated_issue_types=("ISSUE_OD_DUPLICATE",),
                triggered_issue_types=("ISSUE_OD_DUPLICATE",),
                summary="전방 차량 bbox 중복 이슈",
                observed_evidence="raw/qv/bev/json",
                inference="OD fail",
                uncertainty="single frame",
                candidate_adjudications=(
                    CandidateAdjudication(
                        candidate_id="CANDIDATE_ISSUE",
                        feature="OD",
                        issue_type="ISSUE_OD_DUPLICATE",
                        object_ids=("172", "182"),
                        result="issue",
                        checked_planes=("raw", "ics", "bev_vcs", "json"),
                        summary="중복 후보 유지",
                    ),
                ),
            ),
        )
    )

    xlsx_path = write_result_xlsx(
        tmp_path / "output/result.xlsx",
        [package],
        results={package.package_id: result},
    )
    sheet = load_workbook(xlsx_path)["feature_results"]
    headers = [cell.value for cell in sheet[1]]
    row = {header: sheet.cell(row=2, column=index + 1).value for index, header in enumerate(headers)}

    assert row["ics_crop_image"].endswith("OD__ics.jpg")
    assert row["bev_crop_image"].endswith("OD__bev.jpg")
    assert "candidate_evidence_artifacts" not in headers

    html_path = write_summary_html(
        tmp_path / "output/summary.html",
        [package],
        results={package.package_id: result},
    )
    html = html_path.read_text(encoding="utf-8")
    assert "[Crop 산출물]" in html
    assert "기능 ICS crop" in html
    assert "기능 BEV crop" in html
    assert "후보 ICS crop" not in html
    assert "후보 BEV crop" not in html


def test_write_result_xlsx_includes_tool_error_row(tmp_path):
    error = ToolError(
        code="missing_video",
        problem="video path does not exist",
        location="row 2 video_path",
        cause="file not found",
        fix="check the path",
        case_id="CASE_BAD",
    )
    output_path = write_result_xlsx(tmp_path / "output/result.xlsx", [], errors=[error])

    workbook = load_workbook(output_path)
    sheet = workbook["results"]
    headers = [cell.value for cell in sheet[1]]
    row = {header: sheet.cell(row=2, column=index + 1).value for index, header in enumerate(headers)}
    assert row["case_id"] == "CASE_BAD"
    assert row["frame_result"] == "fail"
    assert row["judgment"] == "tool_error"


def test_write_summary_html_links_evidence_and_errors(tmp_path):
    package = _package(tmp_path)
    result = PackageReviewResult(
        judgment=Judgment.POTENTIAL_ISSUE,
        confidence=Confidence.LOW,
        suspicious_type=SuspiciousType.VALUE_JUMP,
        review_priority=ReviewPriority.HIGH,
        summary="distance value jumped",
        observed_evidence="raw and QV disagree near ego path",
        inference="potential distance_or_position issue",
        uncertainty="needs adjacent frame review",
        feature_results=(
            FeatureReviewResult(
                feature="OD",
                result=FrameTestResult.FAIL,
                confidence=Confidence.LOW,
                evaluated_issue_types=("ISSUE_OD_DUPLICATE", "ISSUE_OD_CLASS"),
                triggered_issue_types=("ISSUE_OD_DUPLICATE",),
                summary="OD distance value jumped",
                observed_evidence="OD object position differs between raw/QV/JSON",
                inference="OD feature fails this frame",
                uncertainty="needs adjacent frame review",
            ),
            FeatureReviewResult(
                feature="LD",
                result=FrameTestResult.PASS,
                confidence=Confidence.MEDIUM,
                evaluated_issue_types=("ISSUE_LD_MISSING", "ISSUE_LD_FALSE_POSITIVE"),
                triggered_issue_types=(),
                summary="LD lane evidence is acceptable",
                observed_evidence="lane overlay follows visible lane markings",
                inference="LD passes this frame",
                uncertainty="none from this sample",
            ),
        ),
    )
    error = ToolError(
        code="missing_video",
        problem="video path does not exist",
        location="row 2 video_path",
        cause="file not found",
        fix="check the path",
        case_id="CASE_BAD",
    )

    output_path = write_summary_html(
        tmp_path / "output/summary.html",
        [package],
        results={package.package_id: result},
        errors=[error],
    )
    html = output_path.read_text(encoding="utf-8")

    assert "CASE_001 · Frame 100" in html
    assert "FAIL" in html
    assert "PASS" in html
    assert "OD" in html
    assert "LD" in html
    assert "CASE_001 frame 100 OD는 raw/ICS(QV)/BEV/JSON 4-plane 검토 결과 ISSUE_OD_DUPLICATE 이슈가 확인되어 fail입니다." in html
    assert "CASE_001 frame 100 LD는 raw/ICS(QV)/BEV/JSON 4-plane 검토 결과 ISSUE_LD_MISSING, ISSUE_LD_FALSE_POSITIVE에서 단일 프레임 기준 결함이 확인되지 않아 pass입니다." in html
    assert "ISSUE_OD_DUPLICATE" in html
    assert "기능 검토 리포트" in html
    assert "판단 근거" in html
    assert "[이슈 요약]" in html
    assert "[판단 근거]" in html
    assert "[관찰 증거]" not in html
    assert "[불확실성]" in html
    assert "[검출 이슈]" in html
    assert "[평가 이슈]" in html
    assert "fail로 판정합니다" in html
    assert "pass로 판정합니다" in html
    assert "QV 오버레이" in html
    assert "원본 프레임" in html
    assert "QV 프레임" in html
    assert "JSON" in html
    assert "raw_frames/frame_00000100.jpg" in html
    assert "qv_frames/frame_00000100.jpg" in html
    assert "json_snippets/frame_00000100.json" in html
    assert "priority" not in html.lower()
    assert "frame_00000100.jpg" in html
    assert "CASE_BAD" in html
    assert "overflow-wrap: anywhere" in html
    assert "max-height: 220px" in html


def test_write_summary_html_reports_only_issue_candidate_adjudications(tmp_path):
    package = _package(tmp_path)
    result = PackageReviewResult(
        feature_results=(
            FeatureReviewResult(
                feature="OD",
                result=FrameTestResult.FAIL,
                confidence=Confidence.HIGH,
                evaluated_issue_types=("ISSUE_OD_DUPLICATE",),
                triggered_issue_types=("ISSUE_OD_DUPLICATE",),
                summary="전방 원거리 차량 영역에서 172-182 OD BBOX 중복 검출 이슈",
                candidate_adjudications=(
                    CandidateAdjudication(
                        candidate_id="CANDIDATE_CLEARED",
                        feature="OD",
                        issue_type="ISSUE_OD_DUPLICATE",
                        object_ids=("171", "183"),
                        result="cleared",
                        checked_planes=("raw", "ics", "bev_vcs", "json"),
                        summary="171-183 is cleared by BEV/VCS separation.",
                    ),
                    CandidateAdjudication(
                        candidate_id="CANDIDATE_ISSUE",
                        feature="OD",
                        issue_type="ISSUE_OD_DUPLICATE",
                        object_ids=("172", "182"),
                        result="issue",
                        checked_planes=("raw", "ics", "bev_vcs", "json"),
                        summary="172-182 is confirmed as OD bbox duplication.",
                    ),
                ),
            ),
        )
    )

    output_path = write_summary_html(
        tmp_path / "output/summary.html",
        [package],
        results={package.package_id: result},
    )
    html = output_path.read_text(encoding="utf-8")

    assert "CANDIDATE_ISSUE" not in html
    assert "CANDIDATE_CLEARED" not in html
    assert "cleared" not in html
    assert "전방 원거리 차량 영역에서 172-182 OD BBOX 중복 검출 이슈" in html


def test_write_summary_html_hides_placeholder_review_when_vlm_result_missing(tmp_path):
    package = _package(tmp_path)

    output_path = write_summary_html(tmp_path / "output/summary.html", [package])
    html = output_path.read_text(encoding="utf-8")

    assert "frame/context evidence generated; VLM not run" not in html
    assert "no qualitative issue inference made in Phase 1" not in html
    assert "기능별 평가" not in html
    assert "프레임 단위 메모" not in html
    assert "LLM review result has not been loaded for this frame." not in html
    assert "JSON 스니펫 열기" not in html
    assert "json_snippets/frame_00000100.json" in html
    assert "objects=2; lanes=1" not in html
