# Auto VLM Project Structure

This project is organized around the Auto VLM tester workflow:

```text
input workbook
  -> evidence package
  -> VLM-ready review packet
  -> assistant-authored feature review results
  -> final test report
```

## Runtime Modules

```text
auto_vlm/
  cli.py
    Command-line entry point.

  inputs/
    Read or discover user-provided test inputs.
    Excel cases, local real-data discovery, and input workbook generation live here.

  conversion/
    Convert source media/data into usable artifacts.
    Video metadata, center-frame extraction, raw h264 remux, and frame JSON matching live here.

  sampling/
    Decide which frame numbers should be reviewed for each case.

  evidence/
    Build normalized FrameEvidencePackage objects from converted artifacts.

  vlm/
    Define the VLM review contract and write VLM-ready packet files.
    Review execution and result loading live behind this boundary.

  reports/
    Write final human-facing outputs such as result.xlsx and summary.html.
    These are generated only after review results are loaded.

  pipeline/
    Coordinate the end-to-end batch flow.
    This layer should orchestrate stages, not own detailed business logic.

  models/
    Dataclasses and enums shared across stages.

  utils/
    Shared errors and small helpers.
```

## Support Folders

```text
scripts/
  Thin wrappers for local smoke runs and developer utilities.
  Reusable workflow logic should live under auto_vlm/, not stay in scripts/.

tests/
  Unit and integration tests for the runtime modules.

  docs/
  Requirements, references, runbooks, and coverage notes.

  Active operational docs:
    docs/testing/WORKBOOK_RUNBOOK.md
    docs/references/regression_issue_types/
    docs/references/qualification_visualizer_output_info.md

  Development coverage docs:
    docs/testing/AUTO_VLM_TEST_COVERAGE.md

outputs/
  Generated local run artifacts. Not part of the source architecture.

test_video/
  Local user-provided sample data. Not part of the source architecture.
```

## Boundary Rules

```text
inputs     : create EvaluationCase inputs or discover local data.
conversion : produce frame/json/media artifacts from source files.
sampling   : choose frame indexes.
evidence   : package artifacts into model-safe review units.
vlm        : define/write review requests and later execute VLM review.
reports    : render reviewable outputs.
pipeline   : call the stages in order and collect results/errors.
```

If a module starts doing work from several rows above, split it before adding more behavior.

## Source Of Truth Rules

```text
Feature judgment criteria:
  docs/references/regression_issue_types/

QV/JSON interpretation:
  docs/references/qualification_visualizer_output_info.md

Machine-enforced behavior:
  auto_vlm/ code + tests/

Generated artifacts:
  outputs/ only
```
