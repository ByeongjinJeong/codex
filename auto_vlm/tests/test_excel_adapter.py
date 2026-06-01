from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from auto_vlm.inputs.excel import load_cases
from auto_vlm.models.cases import SamplingMode


def _write_workbook(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_valid_excel_row_becomes_evaluation_case(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    _write_workbook(
        workbook_path,
        [
            "case_id",
            "video_path",
            "raw_video_path",
            "sampling_frame",
            "json_dir",
            "project_type",
            "frame_list",
            "focus_feature",
            "frame_metadata",
            "memo",
            "campaign",
        ],
        [
            [
                "CASE_001",
                "sample.mp4",
                "sample.h264",
                "",
                "json",
                "APTIV_FVC",
                "100,250,480",
                "OD,RBD",
                "sw_version=2026.05; weather=night",
                "broad scan",
                "night_regression",
            ]
        ],
    )

    result = load_cases(workbook_path)

    assert result.errors == []
    assert len(result.cases) == 1
    case = result.cases[0]
    assert case.case_id == "CASE_001"
    assert case.input_source_type == "excel"
    assert case.qv_video_path == Path("sample.mp4")
    assert case.raw_video_path == Path("sample.h264")
    assert case.input_source_path == workbook_path
    assert case.sampling_request.frame_list == (100, 250, 480)
    assert case.sampling_request.sampling_frame is None
    assert case.sampling_request.mode == SamplingMode.EXPLICIT_FRAMES
    assert case.focus_feature == "OD,RBD"
    assert case.frame_metadata["sw_version"] == "2026.05"
    assert case.external_metadata["campaign"] == "night_regression"


def test_missing_required_column_returns_error(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    _write_workbook(workbook_path, ["case_id", "sampling_frame"], [["CASE_001", 20]])

    result = load_cases(workbook_path)

    assert result.cases == []
    assert result.errors[0].code == "excel_missing_required_columns"
    assert "video_path or qv_video_path" in result.errors[0].cause


def test_qv_video_path_can_replace_legacy_video_path(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    _write_workbook(
        workbook_path,
        ["case_id", "qv_video_path", "raw_video_path", "sampling_frame"],
        [["CASE_001", "overlay.mp4", "raw.h264", 50]],
    )

    result = load_cases(workbook_path)

    assert result.errors == []
    assert result.cases[0].video_path == Path("overlay.mp4")
    assert result.cases[0].qv_video_path == Path("overlay.mp4")
    assert result.cases[0].raw_video_path == Path("raw.h264")


def test_missing_required_cell_returns_row_error_and_continues(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    _write_workbook(
        workbook_path,
        ["case_id", "video_path", "sampling_frame"],
        [["", "bad.mp4", 20], ["CASE_002", "ok.mp4", 5]],
    )

    result = load_cases(workbook_path)

    assert len(result.cases) == 1
    assert result.cases[0].case_id == "CASE_002"
    assert len(result.errors) == 1
    assert "case_id" in result.errors[0].cause
    assert result.errors[0].batch_status == "continue"


def test_invalid_frame_list_returns_actionable_error(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    _write_workbook(
        workbook_path,
        ["case_id", "video_path", "sampling_frame", "frame_list"],
        [["CASE_001", "sample.mp4", "", "100,abc,200"]],
    )

    result = load_cases(workbook_path)

    assert result.cases == []
    assert result.errors[0].code == "excel_row_invalid"
    assert "frame_list" in result.errors[0].cause


def test_numeric_frame_list_with_excel_comma_format_is_treated_as_list(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["case_id", "video_path", "sampling_frame", "frame_list"])
    sheet.append(["CASE_001", "sample.mp4", "", 153235])
    sheet["D2"].number_format = "#,##0"
    workbook.save(workbook_path)

    result = load_cases(workbook_path)

    assert result.errors == []
    assert result.cases[0].sampling_request.frame_list == (153, 235)


def test_invalid_sampling_frame_returns_error(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    _write_workbook(
        workbook_path,
        ["case_id", "video_path", "sampling_frame"],
        [["CASE_001", "sample.mp4", -1]],
    )

    result = load_cases(workbook_path)

    assert result.cases == []
    assert "sampling_frame" in result.errors[0].cause


def test_frame_list_and_sampling_frame_are_mutually_exclusive(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    _write_workbook(
        workbook_path,
        ["case_id", "video_path", "sampling_frame", "frame_list"],
        [["CASE_001", "sample.mp4", 50, "100,200"]],
    )

    result = load_cases(workbook_path)

    assert result.cases == []
    assert "exactly one of frame_list or sampling_frame" in result.errors[0].cause


def test_invalid_focus_feature_returns_error(tmp_path):
    workbook_path = tmp_path / "cases.xlsx"
    _write_workbook(
        workbook_path,
        ["case_id", "video_path", "sampling_frame", "focus_feature"],
        [["CASE_001", "sample.mp4", 1, "BAD_FEATURE"]],
    )

    result = load_cases(workbook_path)

    assert result.cases == []
    assert result.errors[0].code == "excel_row_invalid"
    assert "focus_feature must contain only" in result.errors[0].cause
