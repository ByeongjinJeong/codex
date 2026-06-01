# Auto VLM Session Handoff

Last updated: 2026-06-01

## Current Goal

Prepare the next session to implement a real feature-level VLM review
orchestration harness. The current issue is not missing prompt prose. The issue
is that long markdown instructions are not being executed as reliable stages
with validation, retry, and cross-feature audit.

## Working Directory

```text
C:\Users\Byeongjin Jeong\codex\auto_vlm
```

Git status:

```text
No git repository is present in this folder.
```

## Source Of Truth

```text
AGENTS.md
  Root operating rules.

docs/WORK_UNITS.md
  Durable work order for feature-level review orchestration.

docs/testing/AUTO_VLM_WORKBOOK_RUN_WORKFLOW.md
  Workbook execution workflow.

docs/references/regression_issue_types/
  OD/LD/RBD/TS/TL issue criteria.

docs/references/qualification_visualizer_output_info.md
  QV/JSON interpretation.

auto_vlm/ + tests/
  Machine-enforced behavior.

outputs/
  Generated artifacts only. Not durable source of truth.
```

## Key Decision From Current Discussion

The fix is not to keep adding more instructions to long markdown packets.

Correct direction:

```text
1. Split prompts by package + feature.
2. Run feature-level review tasks.
3. Validate coverage deterministically.
4. Run a lightweight cross-feature audit.
5. Merge validated feature verdicts.
6. Generate final reports from feature verdicts only.
```

Important distinction:

```text
Report regression:
  fixed llm_review_results.json -> stable result.xlsx / summary.html

VLM evaluation:
  model sees evidence -> generates feature results -> validator/audit/report
```

Do not call fixed expected fail rows a VLM correctness test.

## Recent Diagnostic State

The user corrected multiple review misses in `input_cases.xlsx`. The final
manual review artifact currently says:

```text
CASE_001__frame_00000520 | LD  | DEF-LD-RBD-LOCALIZATION
CASE_002__frame_00000153 | OD  | DEF-OD-BBOX-FIT
CASE_002__frame_00000153 | RBD | DEF-LD-RBD-FN
CASE_002__frame_00000235 | OD  | DEF-OD-BBOX-DUP
CASE_002__frame_00000235 | RBD | DEF-LD-RBD-FN
```

This is useful as diagnostic context, not as a general VLM correctness oracle.
The user explicitly noted that they cannot provide issue labels for new cases.

## Files Changed In Current Context

Known changed/added files from the recent session:

```text
auto_vlm/cli.py
auto_vlm/pipeline/engine.py
auto_vlm/pipeline/manifest.py
auto_vlm/pipeline/run_inspector.py
auto_vlm/reports/excel_report.py
auto_vlm/reports/html_report.py
auto_vlm/vlm/review_validator.py
tests/test_engine.py
tests/test_reports.py
tests/test_run_inspector.py
tests/test_input_cases_golden.py
docs/WORK_UNITS.md
docs/SESSION_HANDOFF.md
```

Generated artifacts updated under:

```text
outputs/excel_test_run_latest/
```

Do not treat generated outputs as source. They may be useful for local manual
inspection but are ignored by `.gitignore`.

## Recent Verification

Commands run successfully:

```text
python -m pytest tests/test_input_cases_golden.py -q
  -> 1 passed

python -m pytest tests/test_reports.py tests/test_engine.py tests/test_vlm_results.py -q
  -> 38 passed
```

Final workbook run also succeeded:

```text
python -m auto_vlm.cli run --input input_cases.xlsx \
  --output outputs\excel_test_run_latest \
  --review-results outputs\excel_test_run_latest\llm_review_results.json \
  --reuse-existing-artifacts

-> result.xlsx generated
-> summary.html generated
-> packages: 3
-> review_results: 3
-> errors: 0
-> review_quality_status: passed
```

## Current Risks

```text
1. tests/test_input_cases_golden.py is misleading if treated as VLM evaluation.
   It should be removed or renamed as report regression in WU-20.

2. Existing markdown review packets are still too broad.
   They should not be expanded further as the main fix.

3. Current review results are manually authored.
   They do not prove a VLM runner can find the same issues on new cases.

4. Candidate artifacts can distract from full feature sweep.
   Candidate must remain an internal hint, not the final report structure.
```

## Next Concrete Step After Clear

Start with `harness-workflow`, then read:

```text
AGENTS.md
docs/WORK_UNITS.md
docs/SESSION_HANDOFF.md
```

Then run:

```text
python -m pytest tests/test_reports.py tests/test_engine.py tests/test_vlm_results.py -q
```

First implementation unit:

```text
WU-20. Remove Or Rename Misleading Golden VLM Test
```

Expected action:

```text
- Review tests/test_input_cases_golden.py.
- Do not keep it as a VLM correctness test.
- Either remove it, or rename/reword it as fixed review-result report
  propagation.
- Then proceed to WU-21 feature review task JSON.
```

## Work Order Summary

Planned units:

```text
WU-20 Remove Or Rename Misleading Golden VLM Test
WU-21 Feature Review Task JSON
WU-22 Feature VLM Runner Interface
WU-23 Coverage Validator
WU-24 Cross-Feature Audit
WU-25 Report Final Verdict Only
WU-26 End-To-End Workbook Review Command
```

The central architecture decision:

```text
Do not ask one long prompt to solve the whole workbook.
Run one package + one feature at a time, then validate and audit.
```

## Suggested Resume Prompt

After `/clear`, use:

```text
Resume with harness-workflow in C:\Users\Byeongjin Jeong\codex\auto_vlm.
Read AGENTS.md, docs/WORK_UNITS.md, docs/SESSION_HANDOFF.md, then start WU-20.
```
