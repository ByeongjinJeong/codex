# Auto VLM Work Units

Last updated: 2026-06-01

This is the durable work order for the next session. Do not rely on chat
history. The current problem is not that the issue criteria are absent; the
problem is that the criteria are not executed by an orchestrated review harness.

## Project Goal

Auto VLM should run workbook cases through an explicit staged workflow:

```text
input workbook
  -> raw/QV/JSON evidence
  -> feature-level VLM review tasks
  -> feature-level VLM results
  -> deterministic coverage validation
  -> frame-level cross-feature audit
  -> final feature verdict report
```

The product must behave consistently on new unseen cases. It must not require
the user to identify the issue first. User feedback on `input_cases.xlsx` is an
example of failures to prevent generally, not a hard-coded answer key.

## Source Planning Artifacts And Instructions

```text
Root instructions:
  AGENTS.md

Workbook workflow:
  docs/testing/AUTO_VLM_WORKBOOK_RUN_WORKFLOW.md

Feature judgment criteria:
  docs/references/regression_issue_types/

QV/JSON interpretation:
  docs/references/qualification_visualizer_output_info.md

Existing planning docs:
  docs/planning/AUTO_VLM_LLM_REVIEW_WORKFLOW_AUTOPLAN.md
  docs/planning/AUTO_VLM_FEATURE_REVIEW_CONTEXT_AUTOPLAN.md

Machine-enforced behavior:
  auto_vlm/ code + tests/

Generated artifacts:
  outputs/
```

## Current Diagnosis

The current system can build evidence and reports, but the actual judgment step
is not orchestrated well enough.

```text
What exists:
  - Excel adapter
  - evidence package generation
  - markdown review packets
  - review_tasks.json
  - llm_review_results.json loader
  - result.xlsx / summary.html writers

What is missing:
  - feature-level VLM runner
  - per-feature small prompt execution
  - machine-readable coverage audit
  - cross-feature contradiction audit
  - retry semantics for only failed/missing feature reviews
```

Repeated failure mode seen in `input_cases.xlsx`:

```text
1. Long markdown instructions existed.
2. The reviewer still focused on the most visible candidate hints.
3. Candidate-free visible issues were missed.
4. User correction caused overfitting to the newest user statement.
5. Results changed repeatedly instead of following a stable review protocol.
```

This is an orchestration failure, not a user-spec failure. Do not fix it by
adding more prose to the markdown packets.

## Scope Boundaries

In scope:

```text
- Split review execution by package + feature.
- Build small feature prompts from existing criteria and evidence.
- Add deterministic coverage validation.
- Add a lightweight cross-feature audit.
- Keep final reports focused on feature-level verdicts.
- Keep candidate artifacts as internal hints, not final report rows.
- Make reruns idempotent and retryable at feature granularity.
```

Out of scope for the next unit unless explicitly requested:

```text
- Hard-coding expected fail rows as a VLM correctness test.
- Creating a large second reviewer that redoes the whole VLM review.
- Adding more long-form markdown instructions as the primary fix.
- Treating generated outputs as source-of-truth criteria.
- Building a polished UI.
```

## Key Decisions

### D0. Workbook Feature Selection Uses One Column

`input_cases.xlsx` uses `focus_feature` as the single review selector. There is
no separate `review_features` column. The column accepts `ALL`, a single feature
such as `OD`, or comma-separated feature subsets such as `OD,RBD`. The selected
features drive feature evidence packets, feature task JSON, feature responses,
candidate obligations, validation, and final report rows.

### D1. Prompt Work Must Be Split

One large markdown packet is too broad. The correct execution unit is:

```text
one package_id + one feature
```

For each package, run these independently:

```text
OD
LD
RBD
TS
TL
```

Each feature prompt should include only:

```text
- package metadata
- raw frame path
- QV/ICS feature crop path
- BEV/VCS feature crop path
- JSON snippet path
- JSON summary
- feature-specific issue type checklist
- candidate hints for that feature only
- required output schema
```

### D2. Candidate Is An Internal Hint

Candidate artifacts help guide inspection but are not the review structure.

```text
Candidate:
  internal evidence hint

Final report:
  package_id + feature + result + triggered_issue_types + reasoning + evidence links
```

Do not expose candidate adjudication tables as primary report output.

### D3. Post-Review Should Be Thin

Do not add a large second VLM review that repeats all work. Add deterministic
and focused checks:

```text
Coverage validator:
  machine-readable checks

Cross-feature audit:
  small audit over feature verdicts and one full frame/QV context
```

The cross-feature audit asks whether the feature assignment is wrong or
contradictory. It should not redo all detailed feature inspection.

### D4. Golden Fail Rows Are Not A VLM Test

A test that asserts fixed fail rows from a fixed `llm_review_results.json` only
tests report propagation.

```text
Valid use:
  report regression test

Invalid use:
  VLM correctness test
```

The next session should remove or rename any `input_cases` golden test that
pretends to validate VLM judgment. If retained, it must be clearly named as a
report regression test and must not be described as VLM evaluation.

## Runtime Harness

### Stage Map

```text
1. input
   Read workbook and normalize EvaluationCase records.

2. evidence
   Extract raw/QV frames, JSON snippets, feature crops, candidate crops.

3. feature_review_tasks
   Create one task JSON per package + feature.

4. feature_vlm_review
   Execute VLM for each feature task.

5. feature_result_validation
   Validate schema, issue coverage, evidence citations, and no missing features.

6. cross_feature_audit
   Check feature assignment and contradictions at package/frame level.

7. review_result_merge
   Merge validated feature results into llm_review_results.json.

8. reports
   Generate result.xlsx and summary.html from final feature verdicts.
```

### Stage Contracts

```text
input
  input: input_cases.xlsx
  output: list[EvaluationCase]
  failure: adapter errors with row locations

evidence
  input: EvaluationCase
  output: FrameEvidencePackage artifacts
  failure: unreadable video, missing frame, JSON parse/match issues

feature_review_tasks
  input: FrameEvidencePackage
  output: model/tasks/<package_id>/<feature>.json
  failure: missing evidence path or criteria mapping

feature_vlm_review
  input: one feature task JSON + image refs
  output: model/responses/<package_id>/<feature>.json
  failure: provider error, invalid JSON, timeout, refusal

feature_result_validation
  input: feature response JSON
  output: validated feature result or retryable error
  failure: missing issue types, missing evidence planes, invalid enums

cross_feature_audit
  input: all feature results for one package + one full QV/RAW context
  output: accept/revise/rerun recommendation
  failure: unresolved feature conflict

review_result_merge
  input: accepted feature results
  output: llm_review_results.json
  failure: missing feature or unresolved audit

reports
  input: packages + llm_review_results.json
  output: result.xlsx, summary.html, manifest.json
  failure: writer/load errors, but reports should still be generated when
           review results exist unless the result JSON is unreadable
```

### Artifact Layout

Use a run-scoped layout. Current `outputs/<run_id>/` may remain, but the model
subtree should become explicit:

```text
outputs/<run_id>/
  manifest.json
  review_tasks.json                 # batch index, optional compatibility
  llm_review_results.json            # merged final result
  cases/
    <case_id>/
      raw_frames/
      qv_frames/
      json_snippets/
      feature_evidence/
      candidate_evidence/
      feature_packets/
      candidate_packets/
      vlm_packets/
  model/
    tasks/
      <package_id>/
        OD.json
        LD.json
        RBD.json
        TS.json
        TL.json
    responses/
      <package_id>/
        OD.json
        LD.json
        RBD.json
        TS.json
        TL.json
    validation/
      <package_id>/
        OD.json
        LD.json
        RBD.json
        TS.json
        TL.json
    audits/
      <package_id>.json
    token_usage.json
  result.xlsx
  summary.html
```

### Manifest Requirements

Add or preserve these fields:

```text
run_id
created_at
config
inputs
outputs
counts
stages
packages
feature_review:
  tasks_total
  responses_total
  validated_total
  retryable_failures
  non_retryable_failures
cross_feature_audit:
  accepted
  rerun_required
  conflicts
review_provenance
review_quality
errors
```

### Retry/Resume Semantics

Design for these commands or equivalent internal APIs:

```text
--until evidence
--only-feature OD
--only-package <package_id>
--retry-failed-feature-reviews
--reuse-existing-artifacts
--reuse-feature-responses
```

Do not rerun the full workbook when only one feature response failed schema
validation.

## Ordered Work Units

### WU-20. Remove Or Rename Misleading Golden VLM Test

Status: done

Goal:

```text
Correct the test added during the interrupted session. It should not claim to
validate VLM correctness by comparing fixed fail rows.
```

Result:

```text
Removed tests/test_input_cases_golden.py. The fixed input_cases fail-row check
depended on ignored generated artifacts and test videos, and it could be
misread as VLM correctness. Report propagation remains covered by report tests
that construct explicit PackageReviewResult fixtures.
```

Files touched:

```text
tests/test_input_cases_golden.py
docs/WORK_UNITS.md
docs/SESSION_HANDOFF.md
```

Acceptance criteria:

```text
- No test describes fixed expected fail rows as VLM evaluation.
- If the test remains, it is named/report-scoped as fixed review-result report
  propagation.
- User-facing docs clearly separate report regression from VLM evaluation.
```

Verification:

```text
python -m pytest tests/test_reports.py tests/test_engine.py tests/test_vlm_results.py -q
```

### WU-21. Feature Review Task JSON

Status: done

Goal:

```text
Create one machine-readable review task per package + feature.
```

Result:

```text
write_review_tasks now preserves the batch review_tasks.json index and also
writes per-feature task artifacts under model/tasks/<package_id>/<feature>.json.
Each feature task includes package_id, task_id, feature, feature-scoped evidence,
issue_types/evaluated_issue_types, required_schema, and feature-local
candidate_hints.
```

Files likely touched:

```text
auto_vlm/vlm/review_tasks.py
auto_vlm/vlm/feature_context.py
auto_vlm/vlm/reference_context.py
auto_vlm/pipeline/engine.py
tests/test_vlm_schema.py
tests/test_engine.py
```

Acceptance criteria:

```text
- Every package emits OD/LD/RBD/TS/TL task JSON.
- Each task includes only feature-relevant criteria and evidence refs.
- Each task has stable task_id, package_id, feature, evidence, issue_types,
  required_schema, and candidate_hints.
- Batch review_tasks.json can index the per-feature task files.
```

Verification:

```text
python -m pytest tests/test_vlm_schema.py tests/test_engine.py -q
```

### WU-22. Feature VLM Runner Interface

Status: done

Goal:

```text
Add an execution interface for feature-level VLM reviews. If provider execution
is not available yet, create a provider boundary and a local/manual response
loader that uses the same artifact contract.
```

Result:

```text
Added FeatureReviewProvider, ManualResponseProvider, run_feature_reviews, and
merge_feature_responses. Manual/provider responses use the same
model/responses/<package_id>/<feature>.json contract. CLI now accepts
--feature-responses and --reuse-feature-responses.
```

Files likely touched:

```text
auto_vlm/vlm/runner.py
auto_vlm/vlm/providers.py
auto_vlm/vlm/result_loader.py
auto_vlm/cli.py
auto_vlm/pipeline/engine.py
tests/test_vlm_results.py
tests/test_cli.py
```

Acceptance criteria:

```text
- Runner processes one task at a time.
- Response artifacts are saved under model/responses/<package_id>/<feature>.json.
- Provider-specific code is isolated behind a small interface.
- Manual/local response mode can be used for tests without network calls.
- CLI exposes a clear review stage command or flag.
```

Verification:

```text
python -m pytest tests/test_vlm_results.py tests/test_cli.py -q
```

### WU-23. Coverage Validator

Status: done

Goal:

```text
Add deterministic validation after feature responses.
```

Result:

```text
Validation now writes model/validation/<package_id>/<feature>.json artifacts
and exposes retryable feature-level failures in review_quality. result_loader
also rejects triggered_issue_types that were not included in evaluated_issue_types.
```

Validation must check:

```text
- All packages have OD/LD/RBD/TS/TL results.
- Each feature evaluates all GT-less applicable issue types.
- Each feature cites raw, ICS/QV, BEV/VCS, and JSON evidence.
- PASS results explain why candidate hints or visible cues are not issues.
- FAIL results include triggered_issue_types and feature-specific reasoning.
- Final result cannot be needs_review.
```

Files likely touched:

```text
auto_vlm/vlm/result_loader.py
auto_vlm/vlm/review_validator.py
tests/test_vlm_results.py
tests/test_engine.py
```

Acceptance criteria:

```text
- Missing feature result fails validation.
- Missing issue type sweep fails validation.
- Missing evidence plane citation fails validation.
- Validator returns retryable failures by package + feature.
```

Verification:

```text
python -m pytest tests/test_vlm_results.py tests/test_engine.py -q
```

### WU-24. Cross-Feature Audit

Status: done

Goal:

```text
Add a lightweight package-level audit that checks whether feature assignment is
wrong or contradictory after all feature results exist.
```

Result:

```text
Added deterministic package-level cross-feature audit artifacts under
model/audits/<package_id>.json. The audit can accept, request a specific feature
rerun, or flag conflicts such as duplicate issue ownership across features.
Manifest records accepted/rerun/conflict counts.
```

Audit should detect cases like:

```text
- OD candidate distracts from an LD localization issue.
- RBD and LD both claim the same issue without clear ownership.
- Feature is PASS while its reasoning says an issue exists.
- Candidate-free visible issue is ignored despite feature evidence.
```

Files likely touched:

```text
auto_vlm/vlm/cross_feature_audit.py
auto_vlm/pipeline/engine.py
auto_vlm/pipeline/manifest.py
tests/test_vlm_results.py
tests/test_engine.py
```

Acceptance criteria:

```text
- Audit artifact is written per package.
- Audit can accept, request a specific feature rerun, or flag conflict.
- Audit does not expose candidate details in final reports.
- Manifest records audit counts and unresolved conflicts.
```

Verification:

```text
python -m pytest tests/test_vlm_results.py tests/test_engine.py -q
```

### WU-25. Report Final Verdict Only

Status: done

Goal:

```text
Ensure final reports show feature verdicts, not internal candidate workflow.
```

Result:

```text
Final report text now omits candidate IDs and candidate adjudication details.
Report tests use synthetic pass-through issue labels where report propagation is
being tested, instead of real workbook-specific expected issue rows.
```

Files likely touched:

```text
auto_vlm/reports/excel_report.py
auto_vlm/reports/html_report.py
tests/test_reports.py
```

Acceptance criteria:

```text
- result.xlsx feature_results sheet contains package_id, feature, result,
  triggered_issue_types, summary, observed_evidence, inference, uncertainty,
  and feature evidence links.
- Candidate adjudication tables are not primary report output.
- HTML summary mirrors feature verdicts.
```

Verification:

```text
python -m pytest tests/test_reports.py -q
```

### WU-26. End-To-End Workbook Review Command

Status: done

Goal:

```text
Provide one command/workflow that runs workbook evidence, feature review,
validation, audit, merge, and report generation.
```

Result:

```text
CLI output now prints the explicit stage list and feature review/audit counts.
The run command supports --feature-responses, --reuse-feature-responses, and
--retry-failed-feature-reviews. inspect-run now requires cross_feature_audit to
be accepted before final_ready can be true. Workbook workflow docs describe
evidence-only stops, manual feature response execution, response reuse, retry,
validation, audit, and final inspection.
```

Files likely touched:

```text
auto_vlm/cli.py
auto_vlm/pipeline/engine.py
auto_vlm/pipeline/manifest.py
docs/testing/AUTO_VLM_WORKBOOK_RUN_WORKFLOW.md
tests/test_cli.py
tests/test_engine.py
```

Acceptance criteria:

```text
- Command stages are explicit in output and manifest.
- It can stop before provider calls.
- It can resume from existing evidence and existing feature responses.
- It can retry only failed feature reviews.
- Final report generation only uses validated and audited feature verdicts.
```

Verification:

```text
python -m pytest
python -m auto_vlm.cli run --input input_cases.xlsx --output outputs/<manual_run>
```

## Verification Strategy

Use separate test classes for separate guarantees:

```text
Unit tests:
  schema, task generation, loader, validator, report writers

Pipeline tests:
  stage contracts, manifest counts, retry/reuse behavior

Report regression tests:
  fixed review_results -> stable result.xlsx / summary.html

VLM evaluation tests:
  provider/manual feature responses -> coverage/audit/report artifacts
  should not be represented as hard-coded expected fail rows unless explicitly
  labeled as benchmark/golden dataset comparison
```

## Skillization Review

Candidate skill:

```text
auto-vlm-review-harness
```

Purpose:

```text
Run and inspect Auto VLM workbook review flows using feature-level VLM
orchestration, coverage validation, cross-feature audit, and final report
generation.
```

Trigger contexts:

```text
- "run input_cases.xlsx"
- "review workbook"
- "VLM test"
- "why did it miss this issue"
- "rerun only failed features"
- "generate final report"
```

What the skill should do:

```text
- Read AGENTS.md, WORK_UNITS.md, SESSION_HANDOFF.md.
- Use the workbook workflow doc.
- Never stop at evidence-only when the user asked for review.
- Use feature-level tasks.
- Distinguish report regression from VLM evaluation.
- Preserve generated artifacts and summarize final feature verdicts.
```

What the skill should not do:

```text
- Hard-code user-provided issue answers as VLM correctness.
- Add more prose-only rules as the primary fix.
- Treat candidate hints as final report rows.
- Patch only one frame when the failure is shared orchestration.
```

Decision:

```text
Track as a candidate now. Create after WU-21 through WU-26 stabilize.
```

## Current Verification Snapshot

As of WU-25 through WU-26:

```text
git diff --check
  -> passed

python -m pytest -q
  -> 119 passed in 3.17s
```

Important caveat resolved in WU-20:

```text
tests/test_input_cases_golden.py was removed because it encoded fixed fail rows
from a fixed review artifact and was not a valid VLM evaluation.
```
