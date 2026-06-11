# Workbook Runbook

Use this document when the user asks to test an Excel workbook, run a VLM test,
or execute the Auto VLM full pipeline from a workbook.

This is the run contract. Keep the execution path narrow: workbook in, packets
reviewed one by one, validated reports out.

## Required Read Order

Before running a workbook test, read these files in order:

```text
AGENTS.md
docs/testing/WORKBOOK_RUNBOOK.md
```

Read these references only when the current packet needs them:

```text
docs/references/adas_vision_review_workflow.md
docs/references/regression_issue_types/od.md
docs/references/regression_issue_types/ld.md
docs/references/regression_issue_types/rbd.md
docs/references/regression_issue_types/ts.md
docs/references/regression_issue_types/tl.md
docs/references/regression_issue_types/review_applicability.md
```

## Pipeline Order

The required flow is:

```text
Excel workbook
  -> input adapter / converter
  -> frame sampling
  -> raw/QV frame extraction
  -> JSON snippet matching
  -> OD evaluation scope annotation
  -> VLM packet generation
  -> packet-by-packet VLM review
  -> packet review responses
  -> coverage validation
  -> llm_review_results.json merge
  -> review-result validation
  -> result.xlsx and summary.html report generation
```

Stopping after `manifest.json`, `review_tasks.json`, or packet markdown is an
incomplete run unless the user explicitly requested evidence generation only.

## Packet Loop

Review work must be performed one packet at a time.

For each generated package:

```text
outputs/<run>/cases/<case>/vlm_packets/<package_id>.md
```

Review the referenced feature packets:

```text
outputs/<run>/cases/<case>/feature_packets/<package_id>/OD.md
outputs/<run>/cases/<case>/feature_packets/<package_id>/LD.md
outputs/<run>/cases/<case>/feature_packets/<package_id>/RBD.md
outputs/<run>/cases/<case>/feature_packets/<package_id>/TS.md
outputs/<run>/cases/<case>/feature_packets/<package_id>/TL.md
```

For each packet, use only the artifacts referenced by that packet:

```text
raw frame
QV/ICS overlay image or crop
BEV/VCS image or crop
JSON snippet
OD evaluation scope annotation, when available
packet markdown instructions
applicable issue-type reference
```

Review only the sampled frame represented by the packet. Do not introduce
adjacent-frame context unless that packet explicitly provides and labels those
artifacts.

## Hard Stops

Do not do any of the following:

```text
- Do not stop at review_tasks.json and call the test successful.
- Do not create llm_review_results.json directly from a batch summary.
- Do not use contact sheets or merged images as a replacement for packet review.
- Do not inspect all raw frames first and infer packet results from that sweep.
- Do not use JSON values or geometry calculations as a shortcut for VLM judgment.
- Do not remove raw/QV/JSON evidence based on OD scope. Scope only controls
  whether an observed OD issue is reportable.
- Do not reuse old llm_review_results.json unless package_id coverage exactly matches the current run.
- Do not generate result.xlsx or summary.html until packet response coverage is complete.
```

Contact sheets or merged panels may be created only as navigation aids. They are
not review evidence and must not be cited as the basis of `llm_review_results.json`.

## Coverage Gate

Before merging results:

```text
- Every package in review_tasks.json has a package-level review.
- Every feature task has one feature result.
- Every feature result includes all required evaluated_issue_types.
- Every feature result cites raw, QV/ICS, BEV/VCS, and JSON evidence.
- OD scope annotation is used only as reportability context, not issue evidence.
- Triggered issue types are included in the parent feature result.
```

If any item is missing, the run is incomplete and reports must not be generated.

## Report Gate

Only after packet review coverage is complete:

```text
1. Merge packet responses into outputs/<run>/llm_review_results.json.
2. Rerun the workbook pipeline with:

   python -m auto_vlm.cli run --input <workbook.xlsx> --output <run> --review-results <run>/llm_review_results.json --reuse-existing-artifacts

3. Confirm:

   review_quality_status: passed
   review_quality_errors: 0
   result_xlsx exists
   summary_html exists
   errors: 0
```

If review validation fails, fix the packet response that caused the failure and
rerun validation/report generation. Do not bypass the validator.

## Completion Criteria

A workbook full pipeline test is complete only when the final response reports:

```text
- input workbook path
- output run directory
- package count
- feature task count
- packet response coverage
- review_quality_status
- result.xlsx path
- summary.html path
- any remaining errors or explicit reason the run is incomplete
```
