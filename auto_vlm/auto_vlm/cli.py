"""Command line interface for Auto VLM."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from auto_vlm.pipeline.engine import run_excel_batch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auto-vlm",
        description="Build GT-less ADAS vision frame evidence packages.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Run an Auto VLM evidence generation batch.",
    )
    run_parser.add_argument(
        "--adapter",
        choices=["excel"],
        default="excel",
        help="Input adapter to use. Phase 1 starts with the Excel adapter.",
    )
    run_parser.add_argument(
        "--input",
        help="Input file path for adapter-based runs, such as cases.xlsx.",
    )
    run_parser.add_argument(
        "--output",
        help=(
            "Output directory for evidence packages and reports. "
            "Defaults to outputs/<input_excel_name>_<yyyyMMdd_HHmmss>."
        ),
    )
    run_parser.add_argument(
        "--review-results",
        help="Optional llm_review_results.json path. Defaults to <output>/llm_review_results.json when present.",
    )
    run_parser.add_argument(
        "--reuse-existing-artifacts",
        action="store_true",
        help="Reuse existing frame/context image artifacts when present and regenerate reports/manifests.",
    )
    return parser


def default_output_dir_for_input(input_path: str | Path, now: datetime | None = None) -> Path:
    """Return the run-scoped default output directory for an input workbook."""
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return Path("outputs") / f"{Path(input_path).stem}_{timestamp}"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        if not args.input:
            parser.error("run requires --input for adapter-based runs.")
        output_dir = Path(args.output) if args.output else default_output_dir_for_input(args.input)
        result = run_excel_batch(
            args.input,
            output_dir,
            review_results_path=args.review_results,
            reuse_existing_artifacts=args.reuse_existing_artifacts,
        )
        if result.result_xlsx:
            print(f"result_xlsx: {result.result_xlsx}")
        else:
            print("result_xlsx: pipeline_incomplete_review_results_missing")
        if result.summary_html:
            print(f"summary_html: {result.summary_html}")
        else:
            print("summary_html: pipeline_incomplete_review_results_missing")
        print(f"manifest_json: {result.manifest_json}")
        if result.review_tasks_json:
            print(f"review_tasks: {result.review_tasks_json}")
        if result.review_results_json:
            print(f"llm_review_results: {result.review_results_json}")
        print(f"review_quality_status: {result.review_quality.status}")
        print(f"review_quality_errors: {len(result.review_quality.errors)}")
        print(f"review_quality_warnings: {len(result.review_quality.warnings)}")
        print(f"packages: {len(result.packages)}")
        print(f"review_results: {len(result.review_results)}")
        print(f"errors: {len(result.errors)}")
        print(f"reused_artifact_packages: {result.reused_artifact_packages}")
        print(f"generated_artifact_packages: {result.generated_artifact_packages}")
        pipeline_complete = (
            bool(result.packages)
            and not result.errors
            and result.result_xlsx is not None
            and result.summary_html is not None
            and result.review_quality.status == "passed"
        )
        return 0 if pipeline_complete else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
