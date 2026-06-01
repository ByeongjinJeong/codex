# Auto VLM Session Handoff

Last updated: 2026-06-01

## Current Goal

Prepare the next session to implement a real feature-level VLM review
orchestration harness. The current issue is not missing prompt prose. The issue
is that long markdown instructions are not being executed as reliable stages
with validation, retry, and cross-feature audit.

## Working Directory

```text
C:\Users\Byeongjin Jeong\codex_github\auto_vlm
```

Git status:

```text
Repository: https://github.com/ByeongjinJeong/codex
Branch: main
Initial auto_vlm snapshot pushed: 6c0407e Add auto_vlm project snapshot
Current status after WU-21 through WU-26:
  Modified code/tests/docs for WU-20 through WU-26.
  New files include vlm/providers.py, vlm/runner.py, vlm/cross_feature_audit.py,
  tests/test_vlm_runner.py, and tests/test_cross_feature_audit.py.
  Full test suite passes.
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

Workbook feature selection:

```text
input_cases.xlsx uses the existing focus_feature column as the only selector.
Do not add review_features.
Accepted examples: ALL, OD, RBD, OD,RBD, OD,LD,RBD.
The selected features drive evidence packets, feature tasks, candidate
obligations, validation, and final report rows.
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

The earlier `input_cases.xlsx` discussion exposed repeated misses, but the
specific corrected rows are intentionally not preserved here as a test oracle.
The durable requirement is to prevent the shared failure mode: candidate hints
must not replace a complete feature sweep over OD/LD/RBD/TS/TL evidence.

## Files Changed In Current Context

Known changed/added files from the recent session before WU-20:

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
docs/WORK_UNITS.md
docs/SESSION_HANDOFF.md
```

Current local changes:

```text
deleted: tests/test_input_cases_golden.py
modified: auto_vlm/cli.py
modified: auto_vlm/pipeline/engine.py
modified: auto_vlm/pipeline/manifest.py
modified: auto_vlm/pipeline/run_inspector.py
modified: auto_vlm/reports/korean_text.py
modified: auto_vlm/vlm/result_loader.py
modified: auto_vlm/vlm/review_tasks.py
modified: auto_vlm/vlm/review_validator.py
added: auto_vlm/vlm/providers.py
added: auto_vlm/vlm/runner.py
added: auto_vlm/vlm/cross_feature_audit.py
modified: tests/test_cli.py
modified: tests/test_engine.py
modified: tests/test_reports.py
modified: tests/test_run_inspector.py
modified: tests/test_vlm_results.py
added: tests/test_vlm_runner.py
added: tests/test_cross_feature_audit.py
modified: docs/planning/AUTO_VLM_LLM_REVIEW_WORKFLOW_AUTOPLAN.md
modified: docs/testing/AUTO_VLM_WORKBOOK_RUN_WORKFLOW.md
modified: docs/WORK_UNITS.md
modified: docs/SESSION_HANDOFF.md
```

Suggested commit message:

```text
Add feature-level review harness stages
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
python -m pytest -q
  -> 119 passed in 3.17s

git diff --check
  -> passed
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
1. Existing markdown review packets are still too broad.
   They should not be expanded further as the main fix.

2. Current review results are manually authored.
   They do not prove a VLM runner can find the same issues on new cases.

3. Candidate artifacts can distract from full feature sweep.
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

Next concrete step:

```text
Review, commit, and push the completed WU-20 through WU-26 changes.
```

Expected action:

```text
- Inspect the full diff for accidental workbook-specific expected issue labels.
- Commit with the suggested message if the diff is acceptable.
- Push to origin/main or create a PR, depending on the user's preference.
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
Resume with harness-workflow in C:\Users\Byeongjin Jeong\codex_github\auto_vlm.
Read AGENTS.md, docs/WORK_UNITS.md, docs/SESSION_HANDOFF.md, then review and ship WU-20 through WU-26.
```
