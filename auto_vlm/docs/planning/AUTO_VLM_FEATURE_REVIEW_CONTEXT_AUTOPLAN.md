# Auto VLM Feature Review Context Office Hours And Autoplan

Date: 2026-05-22

Scope:

```text
FrameEvidencePackage -> feature-specific review context -> VLM feature review
```

This review covers only the missing requirement/design layer between
`FrameEvidencePackage` generation and actual VLM judgment for OD, LD, RBD, TS,
and TL.

## 1. Office Hours Result

### Core User Job

The user does not want a generic VLM to look at frames and guess whether
something is suspicious.

The user wants:

```text
Given one sampled frame/context package, make the VLM inspect each active ADAS
feature with the same reference knowledge a regression tester would use:

- how QV/JSON values should be interpreted
- which fields and rendered overlays belong to each feature
- which issue-type vocabulary applies to that feature
- which observations are strong evidence, weak evidence, or uncertainty
```

### Premise Challenge

Original implicit premise:

```text
FrameEvidencePackage is enough for VLM review if the prompt says:
describe raw scene, describe overlay, compare JSON.
```

Office-hours judgment:

```text
Rejected.
```

Why:

```text
The package contains evidence, but it does not by itself define how to inspect
OD, LD, RBD, TS, or TL. Without feature-specific review context, the VLM can
guess from pixels and generic ADAS knowledge. That creates unstable reviews and
can make the model classify issues before it understands the data.
```

Corrected premise:

```text
FrameEvidencePackage is the evidence unit.
FeatureReviewContext is the judgment instruction unit.
The VLM must receive both.
```

### Narrowest Useful Wedge

Do not build a provider runner first. Do not build a complete rule engine.

The narrowest useful next step is:

```text
Generate deterministic feature-specific review contexts from local reference
documents and include them in VLM review packets.
```

This gives the VLM enough structured domain guidance without claiming GT
accuracy or reimplementing Qualification Visualizer.

## 2. Requirement Decision

### Should This Become A Requirement?

Yes.

This should be added to active requirements because it changes the VLM contract,
not just implementation detail.

Recommended placement:

```text
docs/requirements/AUTO_VLM_REQUIREMENTS.md
  Add a new section after "5. Evidence Requirements":
    "6. Feature Review Context Requirements"

  Then renumber later sections or append as "5A" to minimize churn.
```

Reason:

```text
The current requirements say LLM feature review happens after
FrameEvidencePackage, but they do not define the required feature-specific
knowledge layer. That omission lets implementations send under-specified VLM
prompts.
```

## 3. Proposed Requirement Text

```text
## 5A. Feature Review Context Requirements

Before VLM judgment, each FrameEvidencePackage must be expanded with
feature-specific review context for the requested review lens.

The review context must be deterministic and generated from local reference
documents, not invented by the VLM.

Required reference inputs:

- docs/references/qualification_visualizer_output_info.md
- docs/references/regression_issue_types/common.md
- docs/references/regression_issue_types/<feature>.md

qualification_visualizer_output_info.md is the QV/JSON interpretation guide.
It tells the reviewer which JSON fields, overlay elements, drawing points,
rectangles, counters, IDs, geometry fields, and scene-status fields are relevant.

regression_issue_types/*.md is the feature/issue vocabulary guide. It tells the
reviewer how FN, FP, misclassification, geometry error, distance/position error,
update failure, value jump, ID switch, and related symptoms differ by feature.

The aggregate `regression_feature_issue_type_definitions_en.md` must remain an
index only. The canonical English issue-type content must live in split files so
VLM context construction can load only the relevant feature vocabulary.

The VLM must not assign feature or issue type before inspecting:

1. raw frame/context
2. QV overlay frame/context
3. JSON summary/snippet
4. evidence_integrity
5. the relevant feature review context

For focus_feature=OD, LD, RBD, TS, or TL:

- The primary feature context must be included.
- Other active feature contexts may be omitted from the primary task.
- If a clearly visible anomaly appears outside the focus feature, the VLM may
  record it as a secondary finding with lower confidence unless evidence is
  strong.

For focus_feature=ALL:

- OD, LD, RBD, TS, and TL review contexts must be included.
- The VLM must return feature-level results separately.

The VLM output must separate:

- observed_evidence: facts visible in raw/QV/JSON evidence
- inference: tester interpretation based on feature context
- uncertainty: missing evidence, sync ambiguity, visualizer ambiguity, weak
  visibility, or unsupported field interpretation

The tool must not treat reference documents as ground truth. They are
interpretation and classification guides only.
```

## 4. Autoplan Review

### CEO/Product Review

Verdict:

```text
Accept the requirement.
```

Product reason:

```text
This moves Auto VLM from "image prompt with evidence links" to "regression
tester workflow encoded as review context." That is the actual product value.
```

Scope decision:

```text
Selective expansion.
```

Add the feature review context layer, but do not expand into:

```text
- full provider execution
- GT scoring
- Jira/customer issue validation
- deterministic pass/fail rule engine
- Qualification Visualizer reimplementation
```

### Engineering Review

Recommended architecture:

```text
docs/references/
  qualification_visualizer_output_info.md
  regression_feature_issue_type_definitions_en.md  # index only
  regression_issue_types/
    common.md
    od.md
    ld.md
    rbd.md
    ts.md
    tl.md
    rmd.md
    fs_common.md
    calib.md
    cao.md
    fsd.md
    feature_selection_guide.md
    rule_base_interpretation_guide.md
        |
        v
auto_vlm/vlm/reference_context.py
  load curated QV/JSON excerpts from qualification_visualizer_output_info.md
  load common.md plus the requested feature issue file
  map reference excerpts to active features
        |
        v
auto_vlm/vlm/feature_context.py
  build FeatureReviewContext objects
        |
        v
auto_vlm/vlm/contract.py
  include feature_review_contexts in prompt payload and packet markdown
        |
        v
VLM reviewer
  inspect evidence using feature-specific context
        |
        v
llm_review_results.json
  feature_results: OD/LD/RBD/TS/TL
```

Recommended model additions:

```text
auto_vlm/models/vlm.py
  FeatureReviewContext
    feature: Feature
    qv_json_interpretation: list[str]
    issue_type_guidance: list[str]
    inspection_checklist: list[str]
    must_not: list[str]
```

Recommended module boundaries:

```text
reference_context.py
  Owns source reference loading and curated excerpt lookup.
  Must treat regression_feature_issue_type_definitions_en.md as index only.

feature_context.py
  Owns feature-specific checklist assembly.

contract.py
  Owns VLM payload and markdown rendering only.

pipeline/engine.py
  Should not contain feature judgment logic.
```

### Test Review

Required tests:

```text
tests/test_vlm_feature_context.py
  - focus_feature=OD includes OD context only as primary.
  - focus_feature=ALL includes OD, LD, RBD, TS, TL contexts.
  - unsupported feature is rejected.
  - generated contexts cite allowed local reference sources.
  - contexts contain both QV/JSON interpretation and issue vocabulary guidance.

tests/test_vlm_schema.py
  - build_vlm_prompt_payload includes feature_review_contexts.
  - VLM packet markdown renders feature-specific sections.
  - packet still requires evidence-first reasoning.

tests/test_engine.py
  - generated review packets include context for each package focus_feature.
```

LLM eval requirement when provider execution is later added:

```text
- The model must describe observed evidence before issue classification.
- The model must not invent JSON values absent from json_summary/json_snippet.
- The model must mark sync/visualizer ambiguity separately from likely SW issue.
- The model must not treat reference docs as GT.
```

### DX Review

Developer-facing impact:

```text
Low to medium.
```

The feature context builder should be mostly internal. The CLI should not require
new options for the first version.

Recommended CLI behavior:

```text
auto-vlm run ...
  -> automatically includes feature review context in generated VLM packets
```

Optional future debug flag:

```text
--dump-feature-context
```

Do not add this flag unless debugging context generation becomes painful.

## 5. Failure Modes Registry

```text
+-----+--------------------------------------+--------------------------------------+--------------------------------------+
| ID  | Failure Mode                         | Impact                               | Mitigation                           |
+-----+--------------------------------------+--------------------------------------+--------------------------------------+
| F1  | VLM guesses feature issue from image | unstable false findings              | require FeatureReviewContext         |
| F2  | Issue taxonomy used before evidence  | taxonomy-first hallucination         | evidence-first prompt order          |
| F3  | QV fields misinterpreted             | wrong feature judgment               | QV/JSON interpretation guide         |
| F4  | Context too long                     | high cost, lower model attention     | curated per-feature excerpts         |
| F5  | focus_feature hides visible anomaly  | missed issue outside target lens     | secondary finding policy             |
| F6  | Reference treated as GT              | false certainty                      | explicit "guide only, not GT" rule   |
| F7  | Pipeline owns judgment logic         | brittle architecture                 | keep logic in vlm context modules    |
+-----+--------------------------------------+--------------------------------------+--------------------------------------+
```

## 6. Final Autoplan Decision

Approved recommendation:

```text
Create a requirement section for Feature Review Context before implementing
actual VLM provider execution.
```

Implementation order:

```text
1. Patch AUTO_VLM_REQUIREMENTS.md with Feature Review Context Requirements.
2. Split regression_feature_issue_type_definitions_en.md into canonical
   regression_issue_types/*.md files and keep the aggregate file as an index.
3. Add FeatureReviewContext schema.
4. Add deterministic context builder for OD, LD, RBD, TS, TL.
5. Include feature_review_contexts in VLM prompt payload and markdown packets.
6. Add focused tests.
7. Regenerate one sample VLM packet and inspect manually.
```

Not approved for this step:

```text
- provider runner
- automated final pass/fail issue validation
- full reference parser
- all regression features beyond OD, LD, RBD, TS, TL
```

## 7. Decision Audit Trail

```text
+----+-------+------------------------------------------+--------------------+------------------------------------------+
| #  | Phase | Decision                                 | Classification     | Rationale                                |
+----+-------+------------------------------------------+--------------------+------------------------------------------+
| 1  | OH    | Add FeatureReviewContext layer            | accepted           | FrameEvidencePackage is evidence only    |
| 2  | OH    | Use references before VLM judgment        | accepted           | prevents context-free VLM guessing       |
| 3  | CEO   | Add requirement before implementation     | accepted           | contract-level behavior, not detail      |
| 4  | Eng   | Keep context builder under auto_vlm/vlm   | accepted           | preserves architecture boundaries        |
| 5  | Eng   | Use curated excerpts, not full docs       | accepted           | controls prompt size and attention       |
| 6  | DX    | No new CLI option in first version        | accepted           | keep workflow simple                     |
| 7  | Eng   | Split issue definitions by feature        | accepted           | simpler maintenance and prompt loading   |
+----+-------+------------------------------------------+--------------------+------------------------------------------+
```
