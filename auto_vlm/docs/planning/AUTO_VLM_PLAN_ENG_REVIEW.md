# Auto VLM Plan Eng Review

Last updated: 2026-05-21

Status: LOCKED_FOR_WU_02

Reviewed files:

```text
docs/implementation/AUTO_VLM_PHASE1_TASK_SPEC.md
docs/requirements/AUTO_VLM_REQUIREMENTS.md
docs/testing/AUTO_VLM_TEST_PLAN.md
```

## 1. Scope Challenge

Phase 1 scope is accepted with one constraint:

```text
WU-02 must stop at importable package + CLI help + pytest harness.
Do not start schemas, Excel parsing, video decoding, or report writing in WU-02.
```

Reason:

```text
The project currently has no code. A clean skeleton is the lowest-risk first unit,
and it creates a stable base for WU-03 through WU-07.
```

## 2. Architecture Lock

The Phase 1 architecture is accepted.

```text
Input Adapter
  -> EvaluationCase
  -> Sampler
  -> VideoReader / JsonMatcher
  -> EvidenceBuilder
  -> FrameEvidencePackage
  -> ReportWriter
```

Locked boundaries:

```text
- Excel adapter must not sample frames or read video.
- Sampler must not know Excel column names.
- Video reader must not build report rows.
- Evidence Builder must be the only creator of FrameEvidencePackage.
- Future VLM code must consume FrameEvidencePackage only.
```

## 3. Dependency Decision

Use stdlib `dataclasses` for the first skeleton and early models unless validation
complexity forces Pydantic later.

Phase 1 dependency direction:

```text
Required now:
  pytest

Required when implementing adapters/reports/video:
  openpyxl
  opencv-python

Deferred unless needed:
  pydantic
  pandas
```

Rationale:

```text
Openpyxl is enough for xlsx IO.
Pandas would add unnecessary dataframe behavior before the schema boundary exists.
Dataclasses keep the core model layer simple and explicit.
```

## 4. Test Diagram

```text
WU-02 skeleton
  cli module imports
  cli --help exits 0
  pytest discovers tests

WU-03 schemas
  SamplingRequest validation
  EvaluationCase defaults
  EvidenceIntegrity defaults
  FrameEvidencePackage required fields

WU-04 adapter/sampler
  Excel row -> EvaluationCase
  invalid rows -> ToolError
  frame_list/range/full-video priority

WU-05 evidence/report
  video metadata
  center/context extraction
  package creation
  result.xlsx
  summary.html

WU-06 JSON
  exact filename match
  missing/malformed JSON
  compact summary

WU-07 VLM contract
  structured output validation
  package-only prompt input
```

## 5. Failure Modes

```text
F1. CLI command is ambiguous
  Handling: explicit subcommands and --adapter choices.
  WU-02 test: CLI help smoke test.

F2. Tests require optional video dependencies too early
  Handling: WU-02 tests only import CLI/package.
  WU-02 test: pytest discovery without OpenCV fixture.

F3. Skeleton locks wrong dependency direction
  Handling: no pandas, no Pydantic requirement yet.
  WU-02 test: package metadata only.

F4. Future VLM consumes EvaluationCase directly
  Handling: task spec and work units keep FrameEvidencePackage boundary explicit.
  WU-03/WU-07 tests will enforce this.
```

Critical gaps:

```text
None for WU-02.
Phase 1 critical gaps remain in WU-03 through WU-07 until schemas and tests exist.
```

## 6. Parallelization

Sequential implementation is recommended until WU-03 finishes.

Reason:

```text
The model schema layer is the shared dependency for adapters, sampler, evidence
builder, reports, and VLM contracts. Parallel work before schemas are stable would
mostly create churn.
```

After WU-03:

```text
Lane A: Excel adapter + sampler
Lane B: JSON matcher
Lane C: report writer skeleton
```

These can proceed in parallel if file ownership is kept separate.

## 7. NOT In Scope

```text
- Real video decoding in WU-02: starts in WU-05.
- Excel parsing in WU-02: starts in WU-04.
- Pydantic conversion in WU-02: decide during WU-03 only if dataclasses are insufficient.
- VLM prompt implementation in WU-02: starts in WU-07.
```

## 8. What Already Exists

```text
AGENTS.md
  Provides durable work-unit and handoff rules.

docs/WORK_UNITS.md
  Current source of truth for implementation sequence.

docs/implementation/AUTO_VLM_PHASE1_TASK_SPEC.md
  Concrete task specification.

docs/testing/AUTO_VLM_TEST_PLAN.md
  Test ID mapping and phase exit criteria.
```

## 9. Completion Summary

```text
Scope Challenge: accepted with WU-02 narrowed to skeleton only.
Architecture Review: 0 blocking issues.
Code Quality Review: dependency simplification recommended.
Test Review: WU-02 smoke-test diagram produced.
Performance Review: no WU-02 performance concerns.
Failure modes: 0 WU-02 critical gaps.
Parallelization: sequential until schema layer is complete.
```
