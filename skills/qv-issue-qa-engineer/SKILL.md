---
name: qv-issue-qa-engineer
description: >-
  Run final LLM QA review for Qualification Visualizer issue Excel files. Use
  when a user provides a QV batch Excel with an `issues` sheet and wants an LLM
  to judge each rule-detected issue as real, low-priority, not an issue, or hold,
  using QV-native parsed JSON context and optional issue screenshots.
---

# QV Issue QA Engineer

## Workflow
1. Read the input Excel `issues` sheet.
2. For each row, parse `log_path` + `frame` with QV's native FVC parser:
- `utils.data_processor_fvc.parse_single_fvc_frame`
- `utils/aptiv/aptiv_mapping_config.py`
3. Build a compact issue context containing:
- original rule trigger data from Excel
- target object data from `frame-1`, `frame`, `frame+1`
- CIPV/NIV header values
- key OD signal columns such as long distance, lateral distance, TTC, relative velocity, existence probability, and lane assignment
- JSON file status
- synced screenshot path when `--use-images` is enabled
- QV FVC image legend from `references/qv_image_legend_fvc.md`
4. Route rows with a conservative uncertainty policy:
- `uncertain-only` mode sends only ambiguous rows to Codex CLI
- default policy prioritizes LLM calls for high-impact rows (`priority <= 2`)
- clear-cut real issues and clear-cut non-issues can be pre-judged to save time and tokens
- heading-related rows, boundary TTC rows, ROI-unclear rows, or low-confidence rows are sent to Codex
5. Ask Codex CLI to read the context JSON and write a result JSON file.
6. When screenshots are attached, ask Codex CLI to interpret OD/LD/TS/TL/SOD/FSD/LiDAR overlays using the QV image legend.
7. Judge final label and priority from ADAS/AD control-impact and SOTIF perspectives:
- whether the issue can affect FCW/AEB/ACC target selection, TTC/risk estimation, cut-in gating, lane relevance, trajectory prediction, path planning, or driver/vehicle response
- whether the case shows an intended-function/perception limitation even without component failure
- what severity/impact path makes the issue P1-P5
8. Generate a reviewer-friendly Excel with Korean result columns and Korean QA narrative text.

## Command
```powershell
python "C:\Users\Jihwan Choi\.codex\skills\qv-issue-qa-engineer\scripts\run_qv_issue_qa.py" --input "<INPUT_XLSX>" --mode uncertain-only --use-images
```

Default model: `gpt-5.4-mini`

## Output Sheets
- `최종검토`: primary sheet for final QA review
- `실제이슈`: rows judged as real issues
- `저우선순위`: rows judged as low-priority issues
- `이슈아님`: rows judged as not issues
- `판정실패`: rows where LLM did not produce a valid result file
- `기술컨텍스트`: full context JSON sent to LLM for traceability

## Main Result Columns
- `Decision Mode`: whether the row was auto-resolved or sent to LLM
- `판정결과`: final QA label written by the script
- `우선순위(1~5)`: final QA priority
- Priority scale: `1` is highest impact, `5` is lowest impact
- `이슈요약`: what the original tool rule flagged
- `룰기반근거`: which rule/data caused the issue
- `참조데이터`: values/signals used for final judgment
- `Long Distance [m]`, `Lateral Distance [m]`, `TTC [s]`, `Absolute Longitudinal Velocity [m/s]`, `Absolute Lateral Velocity [m/s]`: key OD signals for quick scanning
- `Issue Signal`: inferred or original problematic signal
- `이미지판단`: image-based judgment when screenshot is attached
- `최종판단`: final QA explanation, including ADAS/AD control impact, SOTIF relevance, severity, and expected impact path when applicable
- `비이슈사유`: required when final decision is not an issue
- `권고조치`: next QA action
- `Routing Reason`: why the row was auto-resolved or sent to LLM
- `LLM오류`: why LLM failed, if it failed

## Options
- `--output <PATH>`: explicit output Excel path
- `--model <MODEL>`: Codex model override; omitted means `gpt-5.4-mini`
- `--max-rows <N>`: sample subset for testing
- `--use-images`: attach synced issue capture images
- `--mode uncertain-only|all`: `uncertain-only` sends only ambiguous rows to Codex; `all` sends every row
- `--llm-priority-max <N>`: in `uncertain-only`, prioritize LLM review for rows with rule priority <= N (default: 2)

## Screenshot Matching
When `--use-images` is enabled:
- first use row `screenshot_path`
- fallback to `<excel_dir>/<excel_stem>/` and match by `frame`, `rule`, or `row_xxxx`

## Screenshot Semantics
- Left side: ICS/original camera view with JSON drawing and LiDAR drawing when available.
- Right side: BEV (bird's-eye view) generated from logs.
- Issue target highlight: yellow box in ICS, yellow circle in BEV, when available.
- Use ICS for visibility, occlusion, edge-of-FOV, and box quality.
- Use BEV for ego path, road edge/median separation, adjacent-lane relevance, and non-drivable area.
- Use `references/qv_image_legend_fvc.md` for QV-native overlay semantics:
- OD labels/classes, CIPV/NIV/TTC text, object distance/velocity text, heading arrows
- LiDAR ICS/BEV boxes and labels
- host/adjacent lanes, road edge, road markings
- FSD/free-space BEV polygon and point classifications
- TS/TL/SOD/construction object labels and colors
- If yellow highlight appears to target the wrong object, report possible capture/target sync risk and rely more on parsed JSON values.
- The LLM should judge as an ADAS/AD camera perception QA engineer: whether the issue can affect autonomous driving control logic, using the left original image and right BEV when available.
- Keep all reviewer-facing text in Korean only. Use English only for short ADAS abbreviations when unavoidable.

## Principle
The LLM is the final judge. The script prepares evidence and validates the output format, but it does not silently replace failed LLM judgment with deterministic fallback QA labels.

## Run Summary
After each run, the script prints a short completion summary with:
- total elapsed time
- number of LLM calls
- total tokens used by Codex CLI

## Reviewer Feedback Memory
Add durable reviewer guidance to:
`references/domain_judgment_guidance.md`

Current guidance includes OD/TTC judgment rules for ego path relevance, road edge or median separation, adjacent-lane objects, edge-of-FOV objects, and non-drivable areas.

## QV Visualization Knowledge
Permanent image interpretation guidance is stored in:
`references/qv_image_legend_fvc.md`

It summarizes useful facts from:
- `utils/aptiv/aptiv_mapping_config.py`
- `utils/aptiv/aptiv_drawing_config_fvc.py`
- `utils/aptiv/aptiv_run_visualization_fvc.py`
