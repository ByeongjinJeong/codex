# Real Data Plumbing Check

Last updated: 2026-05-21

Use this when real QV data is placed under:

```text
C:\Users\Byeongjin Jeong\codex\auto_vlm\test video
```

The folder structure is not trusted. The current plumbing runner discovers:

```text
- largest *.mp4 file as the QV-rendered video
- directory with the most 00000000.json-style files as the frame JSON directory
- largest *.h264 file as the raw source video when present
```

Important correction:

```text
This is not an AI/VLM test success criterion.

The intended judgment workflow needs all three inputs:
  1. raw h264 source video for the real scene
  2. QV-rendered mp4 for overlay/rendered detection output
  3. frame JSON for underlying detection data

QV mp4 + JSON alone only proves extraction/packaging plumbing. The current
runner now remuxes raw .h264 into a seekable .raw.mp4 with ffmpeg -c copy, then
packages raw/QV/JSON evidence together for later AI/VLM review.
```

Run:

```text
python scripts\run_real_data_smoke.py --data-dir "test video" --output outputs\real_data_smoke --sample-count 5
```

Expected outputs:

```text
outputs\real_data_smoke\cases.xlsx
outputs\real_data_smoke\manifest.json
outputs\real_data_smoke\cases\REAL_SMOKE_001\frames\*.jpg
outputs\real_data_smoke\cases\REAL_SMOKE_001\raw_frames\*.jpg
outputs\real_data_smoke\cases\REAL_SMOKE_001\qv_frames\*.jpg
outputs\real_data_smoke\cases\REAL_SMOKE_001\json_snippets\*.json
outputs\real_data_smoke\cases\REAL_SMOKE_001\vlm_packets\*.md
outputs\real_data_smoke\raw_video_cache\*.raw.mp4
```

`result.xlsx` and `summary.html` are final review reports. They are generated
only after `llm_review_results.json` exists and the batch is rerun with review
results.

Interpretation:

```text
packages > 0
  Smoke run succeeded.

errors > 0
  Inspect manifest.json and generated packet paths. Final reports may not exist
  yet if review results were not loaded.

h264 present
  Required for the intended AI/VLM judgment workflow. The runner remuxes it to
  raw_video_cache/*.raw.mp4 with stream copy before frame extraction.
```
