# Auto VLM Test Coverage

This document is for code and pytest coverage planning. It is not an execution
runbook.

For user-requested Excel workbook runs, follow `docs/testing/WORKBOOK_RUNBOOK.md`
instead.

## 1. Strategy

```text
Adapter tests
  source input -> Normalized Evaluation Case

Schema tests
  Evaluation Case / Sampling Request / Frame Evidence Package

Sampler tests
  Evaluation Case -> deterministic sampled frame list

Evidence Builder tests
  sampled frame -> raw center frame / QV center frame / JSON / evidence_integrity / package

Report tests
  packages/results -> result.xlsx and summary.html

VLM tests
  Frame Evidence Package -> structured qualitative judgment
```

Phase 1 must pass without VLM calls.

## 2. Adapter Tests

```text
A1. Valid Excel row
  Given case_id, video_path, and frame_list or sampling_frame
  Expect one Normalized Evaluation Case.

A2. Valid Excel row with JSON
  Given json_dir and project_type
  Expect fields preserved.

A3. Missing required column
  Given missing video_path
  Expect adapter error and no video processing.

A4. Missing required cell
  Given empty case_id
  Expect error with row/cell location and fix.

A5. Invalid frame_list
  Given frame_list = "100,abc,200"
  Expect validation error.

A6. Invalid sampling_frame
  Given negative or non-numeric sampling_frame
  Expect validation error or configured default behavior.

A7. Extra columns
  Unknown columns are preserved as external_metadata.

A8. Empty focus_feature
  Defaults to ALL.

A9. Source traceability
  input_source_type and input_source_path are recorded.
```

## 3. Schema Tests

```text
SC1. Evaluation Case required fields
  Missing case_id/video_path/sampling_request fails validation.

SC2. Sampling Request normalization
  frame_list, range, and sampling_frame are represented consistently.

SC3. Frame Evidence Package required fields
  Missing center_frame_image/video_metadata fails before VLM use.

SC4. evidence_integrity default
  Missing JSON sets json_available=false and does not crash.

SC5. source_case_metadata preservation
  Frame Evidence Package includes source case metadata.
```

## 4. Sampling Tests

```text
S1. frame_list priority
  frame_list provides exact frame ids.

S2. range sampling
  If frame_list is empty, sample by sampling_frame within start_frame/end_frame.

S3. full-video interval sampling
  If no frame_list or range, sample every sampling_frame across the full video.

S4. out-of-range frame
  Clamp or skip with warning.

S5. duplicate removal
  Duplicate sampled frames appear once.

S6. deterministic result
  Same input/config produces same sampled frame list.

S7. short video
  Very short videos produce valid minimal sampling or tool_error.
```

## 5. Evidence Builder Tests

```text
E1. center frame extraction
  Saves deterministic frame image path.

E2. context extraction
  Disabled in the active workflow. Runs should not generate raw_context/qv_context artifacts.

E3. boundary context
  Covered only when a future explicit context mode is added.

E4. context strip
  Not part of the active workflow. Center-frame evidence remains primary.

E5. video metadata
  Records FPS, frame count, width, height.

E6. Frame Evidence Package creation
  Required fields are present.

E7. no JSON package
  Package remains valid with json_available=false.

E8. deterministic output paths
  case_id and sampled_frame determine paths.

E9. reuse evidence
  Existing evidence can be reused when configured.
```

## 6. JSON Tests

```text
J1. exact frame JSON match
  frame 100 maps to 00000100.json.

J2. missing json_dir
  Continues image-based evaluation.

J3. missing frame JSON
  Records missing snippet.

J4. malformed JSON
  Records parse error and continues.

J5. minimum summary
  Produces object/lane/road edge/sign/light/marking/failsafe counts when available.

J6. feature-specific summary
  OD, LD/RBD, TS, TL, FS/COMMON/CALIB summaries include key fields.

J7. raw snippet fallback
  Raw snippet path is linked even when summary is compact.

J8. offset suspicion
  frame_id mismatch or filename mismatch sets evidence_integrity suspicion.
```

## 7. Report Tests

```text
R1. result.xlsx schema
  Includes case_id, video_path, json_dir, project_type, sampled_frame,
  timestamp_sec, focus_feature, judgment, confidence, suspicious_type,
  review_priority, summary, observed_evidence, inference, uncertainty,
  json_summary, evidence_image, json_snippet,
  need_human_review, tool_status, tool_error_message.

R2. HTML evidence links
  Links to center frame and JSON snippet.

R3. category separation
  likely_issue/potential_issue are separated from acceptable.

R4. sync/visualizer separation
  sync_or_visualizer_issue is not mixed with suspected SW issue.

R5. tool_error row
  Broken video records manifest error and batch continues. Final reports require loaded review results.

R6. source traceability
  Report records input source and normalized case metadata.
```

## 8. VLM Schema And Eval Tests

```text
V1. valid structured output
  Response validates against judgment/confidence/feature/suspicious_type enums.

V2. missing field
  Missing observed_evidence, inference, or uncertainty fails validation or is safely repaired.

V3. invalid enum
  Unexpected value is rejected or mapped conservatively.

V4. invented JSON guardrail
  VLM must not cite values absent from JSON summary/snippet.

V5. evidence-first behavior
  VLM describes visible scene before assigning feature/issue type.

V6. sync ambiguity
  Weak integrity leads to sync_or_visualizer_issue or needs_more_evidence.

V7. focus_feature lens
  Obvious non-focus anomalies are still recorded.

V8. no VLM mode
  Evidence generation succeeds without VLM credentials. Final reports require review results.
```

## 9. Failure Coverage

```text
+-----+-------------------------------------+----------------------+
| ID  | Failure mode                        | Tests                |
+-----+-------------------------------------+----------------------+
| F1  | missing video path                  | A3, R5               |
| F2  | unreadable video                    | E5, R5               |
| F3  | invalid frame_list                  | A5                   |
| F4  | frame index out of range            | S4                   |
| F5  | JSON folder missing                 | J2, E7               |
| F6  | frame JSON missing                  | J3                   |
| F7  | malformed JSON                      | J4                   |
| F8  | JSON/video frame offset             | J8, V6               |
| F9  | visualizer module disabled          | V6                   |
| F10 | JSON exists but not drawn           | V6                   |
| F11 | evidence extraction too slow         | E9                   |
| F12 | VLM invents JSON value              | V4                   |
| F13 | focus_feature blindfold             | V7                   |
| F14 | report mixes SW/sync issue          | R4, V6               |
+-----+-------------------------------------+----------------------+
```

## 10. Minimum Phase 1 Exit Criteria

```text
- Excel adapter creates Normalized Evaluation Cases.
- Invalid Excel rows produce actionable errors.
- Sampler produces deterministic sampled frame lists.
- Video metadata is recorded.
- Center images are extracted.
- Frame Evidence Package schema exists and validates.
- evidence_integrity exists, even if some checks are placeholders.
- manifest.json is generated for partial evidence-stage runs.
- result.xlsx and summary.html are generated only after review results are loaded.
- Missing video/JSON/frame errors do not stop the batch.
- VLM calls are not required.
```

## 11. Minimum Phase 2 Exit Criteria

```text
- Exact frame JSON matching works.
- Missing/malformed JSON is reported without stopping.
- Raw JSON snippets are stored or linked.
- Minimum JSON summary is generated.
- Feature-specific compact summaries exist.
```

## 12. Minimum Phase 3 Exit Criteria

```text
- VLM prompt consumes Frame Evidence Package only.
- VLM output validates against structured schema.
- observed_evidence, inference, and uncertainty are separate.
- VLM cannot silently invent JSON values.
- Weak integrity produces conservative judgment.
- result.xlsx/summary.html can be updated with VLM judgment.
```
