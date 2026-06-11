from __future__ import annotations

from datetime import datetime

from auto_vlm.cli import build_parser, default_output_dir_for_input, main


def test_cli_help_exits_successfully(capsys):
    assert main([]) == 0

    captured = capsys.readouterr()
    assert "Build GT-less ADAS vision frame evidence packages." in captured.out


def test_run_command_is_reserved_for_phase1_engine():
    parser = build_parser()

    args = parser.parse_args(
        [
            "run",
            "--adapter",
            "excel",
            "--input",
            "cases.xlsx",
            "--review-results",
            "llm_review_results.json",
            "--reuse-existing-artifacts",
        ]
    )

    assert args.command == "run"
    assert args.adapter == "excel"
    assert args.input == "cases.xlsx"
    assert args.output is None
    assert args.review_results == "llm_review_results.json"
    assert args.reuse_existing_artifacts is True


def test_default_output_dir_uses_excel_name_and_current_datetime():
    output_dir = default_output_dir_for_input(
        r"C:\work\input_cases.xlsx",
        now=datetime(2026, 5, 26, 13, 45, 9),
    )

    assert str(output_dir) == r"outputs\input_cases_20260526_134509"


def test_run_command_requires_input():
    try:
        main(["run"])
    except SystemExit as exc:
        assert exc.code == 2
