# Auto VLM LLM Review Workflow Office Hours And Autoplan

Date: 2026-05-29

Scope:

```text
FrameEvidencePackage
  -> LLM evidence packet
  -> candidate-specific review prompt
  -> llm_review_results.json
  -> LLM-result completeness checks
```

This plan covers only the LLM review workflow. It does not cover Excel parsing,
video extraction, report formatting, deployment, or general pipeline refactors.

## 1. Office Hours Result

### Core User Job

The reviewer does not need a generic VLM answer that says whether a frame looks
suspicious.

The reviewer needs the LLM to behave like an ADAS regression tester:

```text
For every machine-detected candidate, inspect the frame in the same order a
tester uses:

1. raw scene
2. ICS/image overlay
3. BEV overlay/grid
4. JSON physical values as supporting evidence
5. issue/cleared decision
```

The most important user complaint is not that a validator missed a bad output.
The complaint is that the LLM did not actually follow the already-documented
tester workflow.

### Premise Challenge

Rejected premise:

```text
If the VLM packet says "inspect BEV/VCS and JSON," the LLM will reliably do it.
```

Why it fails:

```text
The current packet is a long markdown prompt with a full QV overlay image, raw
image paths, JSON summary, cue text, feature context, and output schema mixed
together. The LLM can read the instruction yet still anchor on the most visible
ICS/image overlap, or substitute JSON long/lat values for actual BEV overlay
inspection.
```

Corrected premise:

```text
The LLM input must be shaped like the tester workflow.

Prompt wording is necessary, but not sufficient. The evidence packet itself must
separate raw, ICS, BEV, and JSON observations by candidate.
```

### Narrowest Useful Wedge

Do not build a full provider runner first. Do not turn the workflow into a rule
engine. Do not start with broad report changes.

The narrowest useful wedge is:

```text
For OD_BBOX_DUP candidates, generate candidate-specific evidence packets that
include raw/ICS/BEV/JSON sections, require mandatory observations before final
decision, and make JSON explicitly secondary to BEV overlay inspection.
```

OD_BBOX_DUP is the right wedge because the failure mode is concrete:

```text
CASE_002 frame 235:
  171-183: cleared because BEV separates them.
  172-182: issue because BEV grid and JSON footprint support duplicate/split
           output on the same left truck.
```

## 2. Current LLM Workflow Findings

### What Already Exists

```text
auto_vlm/vlm/contract.py
  Builds the markdown VLM review packet.

auto_vlm/vlm/review_tasks.py
  Builds review_tasks.json with feature tasks and candidate tasks.

auto_vlm/vlm/candidates.py
  Extracts machine candidate obligations from json_summary.

auto_vlm/vlm/result_loader.py
  Loads llm_review_results.json and checks schema/candidate obligations.

auto_vlm/vlm/review_validator.py
  Checks high-level review quality before final reports.
```

### Current Weaknesses

```text
1. The LLM sees a full QV overlay image, but raw/ICS/BEV are not separated as
   candidate-specific evidence.

2. review_tasks.json is mostly a checklist artifact. It is not the actual LLM
   job manifest or validation source of truth.

3. Candidate reasoning is free text:
   summary / observed_evidence / inference / uncertainty.

4. The output schema allows checked_planes=[raw, ics, bev_vcs, json], but this
   does not prove the LLM inspected the BEV overlay.

5. JSON long/lat can be confused with BEV observation. JSON should support BEV
   inspection, not replace it.
```

## 3. Autoplan Review

### CEO Review

Decision:

```text
Hold scope, but redefine the center of the work.
```

Do not make this a generic "more validation" project. The product quality issue
is that the LLM review experience does not match tester reality.

The 10-star version for the current scope:

```text
When a reviewer opens a candidate packet, the evidence already looks like the
tester's mental checklist:

raw crop -> ICS crop -> BEV crop -> JSON support -> mandatory observations
```

Success is not "the prompt says BEV is required." Success is:

```text
It is hard for the LLM to answer without first producing a BEV observation.
```

### Design Review

No UI scope.

Design still matters at the artifact level. The review packet should be visually
and cognitively scannable:

```text
Candidate-first layout
  Candidate ID
  Why this candidate exists
  Evidence images
  Required observation steps
  Decision rule
```

The current full markdown packet is too broad for candidate-level judgment.

### Engineering Review

Recommended architecture:

```text
FrameEvidencePackage
    |
    v
candidate obligations from json_summary
    |
    v
CandidateEvidencePacket
    |-- raw image / raw crop
    |-- ICS crop or QV candidate crop
    |-- BEV crop
    |-- candidate JSON values
    |
    v
candidate prompt block
    |
    v
llm_review_results.json candidate observations
```

Key engineering decision:

```text
Add candidate evidence generation before changing broad review/report behavior.
```

Reason:

```text
If the LLM still receives one large QV image, prompt changes alone will keep
failing on visually dense frames.
```

### DX Review

Developer-facing scope is limited, but artifact/debug experience matters.

The generated run should make it easy to answer:

```text
What did the LLM see?
Which candidate was reviewed?
Where is the BEV crop?
What did it say about raw/ICS/BEV/JSON?
Why was issue or cleared chosen?
```

Recommended debug paths:

```text
outputs/<run>/cases/<case_id>/candidate_packets/<package_id>/<candidate_id>.md
outputs/<run>/cases/<case_id>/candidate_evidence/<package_id>/<candidate_id>__bev.jpg
outputs/<run>/cases/<case_id>/candidate_evidence/<package_id>/<candidate_id>__ics.jpg
outputs/<run>/cases/<case_id>/candidate_evidence/<package_id>/<candidate_id>__json.json
```

## 4. Final Work Plan

### P0. Rewrite The Candidate Prompt Around Tester Order

Update the LLM task wording so every candidate follows this order:

```text
1. Raw observation
2. ICS observation
3. BEV overlay observation
4. JSON support check
5. Decision
```

Required prompt rule:

```text
JSON physical values support the BEV overlay observation.
They must not replace BEV overlay observation.
```

For OD_BBOX_DUP:

```text
Issue only when raw/ICS and BEV overlay both support same-object duplicate.
Clear when BEV overlay clearly separates the objects.
Mark uncertain when BEV overlay is unreadable.
```

### P0. Generate Candidate-Specific Evidence Packets

Add candidate packet generation for machine-detected candidate obligations.

Initial target:

```text
OD_BBOX_DUP_<left_id>_<right_id>
```

Each candidate packet should include:

```text
candidate_id
package_id
issue_type
object_ids
source cue

raw_frame_image
qv_overlay_frame_image
ics_crop_image
bev_crop_image
candidate_json_values
full_json_snippet
json_summary
```

Candidate packet output should be separate from the broad frame-level packet.

### P0. Add BEV Crop As First-Class Evidence

The LLM should not have to find the BEV grid inside a dense QV frame.

Add a generated BEV crop image for candidate review.

Initial implementation can use deterministic QV layout coordinates for the
current visualizer output. If the crop region is not reliable, the packet must
mark:

```text
bev_crop_status: unavailable_or_unverified
```

and the LLM must not make a confident BEV-based decision.

### P0. Add ICS Crop As Candidate Evidence

Add a candidate-focused ICS/QV crop around the relevant object boxes.

Purpose:

```text
Keep the LLM from scanning a huge full-frame QV image and missing the exact
candidate.
```

The full QV overlay should remain available as reference, but the candidate
prompt should point first to the focused crop.

### P0. Require Mandatory Candidate Observations Before Decision

Change candidate output from one free-text `observed_evidence` field to explicit
observation fields.

Target schema:

```text
candidate_adjudications:
  - candidate_id:
    feature:
    issue_type:
    object_ids:
    raw_observation:
    ics_observation:
    bev_observation:
    json_observation:
    decision: issue | cleared | uncertain
    decision_reason:
    uncertainty:
```

Compatibility option:

```text
Keep summary / observed_evidence / inference for existing reports, but derive
or require them from the structured observations during migration.
```

### P1. Reposition review_tasks.json

Make a clear decision:

```text
review_tasks.json should become the LLM job manifest.
```

It should contain candidate evidence paths and required observation fields.

It should not remain a passive checklist that duplicates packet content but is
not actually used.

### P1. Keep Validator As Safety Net, Not Main Product

Validator should check structure and omissions:

```text
- every candidate obligation has an adjudication
- raw_observation exists
- ics_observation exists
- bev_observation exists
- json_observation exists
- decision is valid
- issue/cleared/uncertain are internally consistent with required fields
```

Validator should not be treated as the main fix. The main fix is better LLM
evidence and prompt flow.

### P1. Regression Baseline

Use `input_cases.xlsx` as a workflow regression fixture.

Required baseline:

```text
CASE_002__frame_00000235
  OD_BBOX_DUP_171_183 -> cleared
  OD_BBOX_DUP_172_182 -> issue
  feature OD -> fail, DEF-OD-BBOX-DUP
```

Run-level expected fail rows after correction:

```text
CASE_002__frame_00000153 | OD  | DEF-OD-BBOX-FIT
CASE_002__frame_00000153 | RBD | DEF-LD-RBD-FN
CASE_002__frame_00000235 | OD  | DEF-OD-BBOX-DUP
```

## 5. Proposed Implementation Units

### Unit 1: Candidate Evidence Model

Files likely affected:

```text
auto_vlm/models/evidence.py
auto_vlm/vlm/candidates.py
auto_vlm/vlm/review_tasks.py
tests/test_vlm_schema.py
tests/test_vlm_results.py
```

Deliverable:

```text
Candidate evidence/task data model that can represent required raw/ICS/BEV/JSON
observation steps.
```

### Unit 2: Candidate Crop Generation

Files likely affected:

```text
auto_vlm/evidence/
auto_vlm/pipeline/engine.py
tests/test_evidence_builder.py
```

Deliverable:

```text
Generated candidate evidence image paths for BEV crop and ICS crop.
```

Risk:

```text
QV layout assumptions may be project-specific. Start with explicit layout
constants and mark crop status when unavailable.
```

### Unit 3: Candidate Packet Prompt

Files likely affected:

```text
auto_vlm/vlm/contract.py
tests/test_vlm_schema.py
```

Deliverable:

```text
Candidate packet markdown that presents raw -> ICS -> BEV -> JSON -> decision.
```

### Unit 4: Structured Candidate Result Loading

Files likely affected:

```text
auto_vlm/models/results.py
auto_vlm/vlm/result_loader.py
auto_vlm/vlm/review_validator.py
tests/test_vlm_results.py
```

Deliverable:

```text
Loader accepts structured candidate observations and rejects missing mandatory
observation steps.
```

### Unit 5: End-To-End Workbook Verification

Files likely affected:

```text
tests/test_cli.py
tests/test_engine.py
docs/testing/AUTO_VLM_WORKBOOK_RUN_WORKFLOW.md
```

Deliverable:

```text
input_cases.xlsx workflow produces final reports with candidate evidence,
structured LLM observations, and final_ready true.
```

## 6. Not In Scope

```text
- Building an actual VLM provider runner.
- Replacing human review with deterministic rule decisions.
- Full QV visualizer redesign.
- UI/report redesign.
- Temporal context reintroduction.
- Generalizing BEV crop extraction to every possible visualizer layout in the
  first pass.
```

## 7. Decision Audit Trail

```text
Decision 1:
  Candidate evidence packet first, provider runner later.
  Reason: the failure is evidence/prompt shape, not provider integration.

Decision 2:
  Start with OD_BBOX_DUP.
  Reason: concrete failure, clear tester workflow, high value.

Decision 3:
  JSON supports BEV; JSON does not replace BEV.
  Reason: prevents the exact failure mode observed in frame 235.

Decision 4:
  review_tasks.json becomes LLM job manifest.
  Reason: passive checklist artifacts create false confidence.

Decision 5:
  Validator remains a safety net.
  Reason: over-validating text does not fix the LLM evidence experience.
```

## 8. Acceptance Criteria

```text
1. Each OD_BBOX_DUP candidate has a candidate-specific packet.

2. Each candidate packet includes raw evidence, ICS evidence, BEV crop evidence,
   and JSON support evidence.

3. The candidate prompt requires raw_observation, ics_observation,
   bev_observation, and json_observation before decision.

4. The prompt explicitly says JSON cannot substitute for BEV overlay inspection.

5. review_tasks.json includes candidate evidence paths and required observation
   fields.

6. llm_review_results.json can represent structured candidate observations.

7. Loader/validator rejects candidate decisions missing BEV observation.

8. CASE_002 frame 235 baseline is preserved:
   171-183 cleared, 172-182 issue.

9. Relevant tests pass.

10. `python -m auto_vlm.cli inspect-run --run-dir <run_dir>` reports:
    final_ready: true
```

## 9. Recommended Execution Order

```text
1. Add candidate evidence/task model.
2. Generate candidate packet markdown without changing report output.
3. Add BEV/ICS crop image paths to candidate packets.
4. Extend llm_review_results candidate schema.
5. Update loader/validator for mandatory observations.
6. Update tests.
7. Rerun input_cases.xlsx workflow.
8. Only after this works, consider broader feature types beyond OD_BBOX_DUP.
```

## 10. Final Recommendation

Proceed with a narrow OD_BBOX_DUP-focused LLM workflow redesign.

Do not continue adding instruction sentences to the broad packet as the primary
solution. The next implementation should make the LLM see the evidence in the
same structure that a tester uses.

