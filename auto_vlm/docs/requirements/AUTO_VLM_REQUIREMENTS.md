# Auto VLM Current Requirements

Last updated: 2026-05-22

## 1. Product Goal

Auto VLM is a GT-less ADAS vision qualitative review tool.

The tool prepares clean frame-level evidence from user-provided test data, then
lets an LLM/VLM reviewer judge whether selected ADAS feature outputs look
acceptable for each sampled frame.

This is not an accuracy metric tool. It must not calculate precision, recall,
mAP, pass rate, or GT-based scoring.

## 2. Current Workflow

```text
input_cases_template.xlsx
  -> EvaluationCase
  -> sampled frames
  -> raw source center frame
  -> QV overlay center frame
  -> matching JSON snippet
  -> FrameEvidencePackage
  -> LLM feature review
  -> review validation
  -> result.xlsx + summary.html
```

## 3. Required Inputs

The active top-level input workbook is:

```text
input_cases_template.xlsx
```

Required columns:

```text
case_id
qv_video_path
raw_video_path
frame_list or sampling_frame
json_dir
focus_feature
```

Notes:

```text
- Exactly one of frame_list or sampling_frame should be filled per row.
- frame_list is used when the user knows exact frames to review.
- sampling_frame is used when the user wants interval sampling; for example,
  50 samples frame 50, 100, 150, ... by default.
- raw_video_path may point to .h264; the pipeline remuxes it to seekable .raw.mp4.
- project_type and memo are not required for the active workflow.
```

## 4. Active Feature Scope

Focus on these features only:

```text
OD
LD
RBD
TS
TL
```

`ALL` is allowed as a review lens, meaning the reviewer should consider the
active feature set broadly.

Supported `focus_feature` values:

```text
ALL
OD
LD
RBD
TS
TL
```

`focus_feature` is a lens, not a blindfold. If a frame is set to `OD` but an
obvious `LD`, `RBD`, `TS`, or `TL` issue is visible, the LLM review may still
record it.

## 5. Evidence Requirements

Each reviewed frame must have:

```text
raw_frame_image
qv_overlay_frame_image
json_snippet
evidence_integrity
```

Adjacent context images are disabled in the active workflow. Reintroduce them
only through an explicit context-mode design with per-frame JSON labeling.

The LLM/VLM review must compare:

```text
1. The real scene from raw source video.
2. The QV-rendered overlay.
3. The frame JSON data.
4. Evidence integrity flags.
```

The tool must not treat QV overlay video alone as enough for real AI/VLM
judgment.

## 5A. Feature Review Context Requirements

Before LLM/VLM judgment, each `FrameEvidencePackage` must be expanded with
feature-specific review context for the requested review lens.

The review context must be deterministic and generated from local reference
documents, not invented by the VLM.

Required reference inputs:

```text
docs/references/qualification_visualizer_output_info.md
docs/references/regression_issue_types/common.md
docs/references/regression_issue_types/<feature>.md
```

Reference roles:

```text
qualification_visualizer_output_info.md
  QV/JSON interpretation guide.
  Explains relevant fields, overlay elements, drawing points, rectangles,
  counters, IDs, geometry fields, and scene-status fields.

regression_issue_types/*.md
  Feature/issue vocabulary guide.
  Explains how FN, FP, misclassification, geometry error,
  distance/position error, update failure, value jump, ID switch, and related
  symptoms differ by feature.
```

The VLM must not assign feature or issue type before inspecting:

```text
1. raw center frame
2. QV overlay center frame
3. JSON summary/snippet
4. evidence_integrity
5. the relevant feature review context
```

For `focus_feature=OD`, `LD`, `RBD`, `TS`, or `TL`:

```text
- Load common.md plus the matching feature file.
- Treat the selected feature as the primary review lens.
- If a clearly visible anomaly appears outside the focus feature, the VLM may
  record it as a secondary finding with lower confidence unless evidence is
  strong.
```

For `focus_feature=ALL`:

```text
- Load common.md plus od.md, ld.md, rbd.md, ts.md, and tl.md.
- Return feature-level results separately.
```

The VLM output must separate:

```text
observed_evidence
  Facts visible in raw/QV/JSON evidence.

inference
  Tester interpretation based on feature context.

uncertainty
  Missing evidence, sync ambiguity, visualizer ambiguity, weak visibility, or
  unsupported field interpretation.
```

The tool must not treat reference documents as ground truth. They are
interpretation and classification guides only.

## 6. LLM Review Output

The next active requirement is to produce structured LLM review results.

Required artifact:

```text
llm_review_results.json
```

Required per-package shape:

```text
package_id
case_id
sampled_frame
feature_results:
  - feature: OD | LD | RBD | TS | TL
    result: pass | fail | needs_review
    confidence: high | medium | low
    summary
    observed_evidence
    inference
    uncertainty
```

Overall frame result rule:

```text
if any feature result is fail:
  frame result = FAIL
else if any feature result is needs_review:
  frame result = NEEDS REVIEW
else:
  frame result = PASS
```

## 7. Report Requirements

`summary.html` is the primary local review artifact.

Workbook runs are expected to continue through feature review, validation, and
final report generation. Evidence-only output is a partial diagnostic mode, not
the default completion state.

It must show:

```text
- Overall frame Result: PASS / FAIL / NEEDS REVIEW
- Feature-level OD/LD/RBD/TS/TL results when actual LLM results exist
- LLM summary, observed evidence, inference, and uncertainty per feature
- Raw center frame and QV overlay center frame
- JSON Evidence as an Open JSON snippet link
```

It must not show:

```text
- Placeholder review text
- Fake feature evaluation when no LLM result exists
- Inline JSON summary unless explicitly requested later
- Provider trial information
```

## 8. Architecture Boundaries

Current source layout:

```text
auto_vlm/
  inputs/       read Excel or discover user data
  conversion/   video, raw h264 remux, frame extraction, JSON matching
  sampling/     decide sampled frames
  evidence/     build FrameEvidencePackage
  vlm/          LLM/VLM contract and review execution
  reports/      result.xlsx and summary.html
  pipeline/     batch orchestration
  models/       shared schemas
  utils/        shared errors/helpers
```

Boundary rules:

```text
- Excel parsing must not perform frame extraction or LLM judgment.
- Pipeline orchestration must not contain detailed feature judgment logic.
- LLM judgment must consume normalized evidence packages, not raw Excel rows.
- Reports must render actual result artifacts, not infer fake judgments.
```

## 9. Out Of Scope For Now

```text
- GT accuracy scoring
- Jira/customer issue verification
- raw model inference
- Qualification Visualizer reimplementation
- all-frame exhaustive review
- multi-model adjudication
- cloud integration requirements
```
