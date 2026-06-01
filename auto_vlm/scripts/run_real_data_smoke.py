from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auto_vlm.conversion.raw_video import normalize_raw_video
from auto_vlm.inputs.real_data import discover_real_data, write_discovered_cases_workbook
from auto_vlm.pipeline.engine import run_excel_batch


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Auto VLM against local real test data.")
    parser.add_argument("--data-dir", default="test video", help="Directory containing mp4/json/h264 test data.")
    parser.add_argument("--output", default="outputs/real_data_smoke", help="Output directory.")
    parser.add_argument("--sampling-frame", type=int, default=50, help="Frame interval for smoke run.")
    parser.add_argument("--raw-fps", type=float, default=30.0, help="FPS to assign when remuxing raw h264.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output)
    discovered = normalize_raw_video(discover_real_data(data_dir), output_dir, fps=args.raw_fps)
    input_xlsx = write_discovered_cases_workbook(output_dir / "cases.xlsx", discovered, args.sampling_frame)
    result = run_excel_batch(input_xlsx, output_dir)

    print(f"qv_mp4_path: {discovered.qv_mp4_path}")
    print(f"raw_h264_path: {discovered.raw_h264_path}")
    print(f"normalized_raw_video_path: {discovered.normalized_raw_video_path}")
    print(f"json_dir: {discovered.json_dir}")
    print(f"json_count: {discovered.json_count}")
    print(f"input_xlsx: {input_xlsx}")
    print(f"result_xlsx: {result.result_xlsx or 'not_generated_review_results_missing'}")
    print(f"summary_html: {result.summary_html or 'not_generated_review_results_missing'}")
    print(f"manifest_json: {result.manifest_json}")
    print(f"review_results: {len(result.review_results)}")
    print(f"packages: {len(result.packages)}")
    print(f"errors: {len(result.errors)}")
    return 0 if result.packages else 1


if __name__ == "__main__":
    raise SystemExit(main())
