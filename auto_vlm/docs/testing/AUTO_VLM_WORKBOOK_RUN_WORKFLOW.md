# Auto VLM Workbook Run Workflow

This is the minimal workflow for workbook runs. Keep the judgment work careful,
but do not add extra process unless the user asks for it.

## Required Path

1. Run evidence generation with the CLI default output directory unless the user
   gives an explicit output path.

   ```text
   python -m auto_vlm.cli run --input <workbook.xlsx>
   ```

2. Review generated feature tasks. A run creates one task per package + feature:

   ```text
   model/tasks/<package_id>/<feature>.json
   ```

   Review can stop here only when the user explicitly asks to stop before
   provider/manual review calls.

3. Provide feature responses with the same package + feature contract:

   ```text
   <manual_responses>/<package_id>/<feature>.json
   ```

   Then run:

   ```text
   python -m auto_vlm.cli run --input <workbook.xlsx> \
     --output <run_dir> \
     --feature-responses <manual_responses> \
     --reuse-existing-artifacts
   ```

   To reuse existing response artifacts without re-executing review:

   ```text
   python -m auto_vlm.cli run --input <workbook.xlsx> \
     --output <run_dir> \
     --reuse-existing-artifacts \
     --reuse-feature-responses
   ```

   To retry only missing/invalid feature responses:

   ```text
   python -m auto_vlm.cli run --input <workbook.xlsx> \
     --output <run_dir> \
     --feature-responses <manual_responses> \
     --reuse-existing-artifacts \
     --retry-failed-feature-reviews
   ```

   Required feature rows after merge:

   ```text
   OD, LD, RBD, TS, TL
   ```

   Required reasoning fields:

   ```text
   summary, observed_evidence, inference, uncertainty
   ```

4. Regenerate final reports from the same run directory when a merged
   `llm_review_results.json` already exists.

   ```text
   python -m auto_vlm.cli run --input <workbook.xlsx> \
     --output <run_dir> \
     --review-results <run_dir>/llm_review_results.json \
     --reuse-existing-artifacts
   ```

5. Inspect the run before reporting to the user.

   ```text
   python -m auto_vlm.cli inspect-run --run-dir <run_dir>
   ```

   Do not call the run final unless `final_ready: true`.

## Mandatory Final Artifacts

Every final report must include these paths in the user-facing answer:

```text
llm_review_results.json
result.xlsx
summary.html
manifest.json
review_tasks.json
```

The `inspect-run` command prints this checklist. Use that output as the final
answer source instead of manually reconstructing artifact paths.

## Quality Boundary

Local validation checks structure and obvious review safety problems:

```text
packages == review_results
errors == 0
review_quality_status == passed
cross_feature_audit_status == accepted
report_mode == final_report
all mandatory artifacts exist
OD/LD/RBD/TS/TL rows exist for every package
machine-detected candidates are adjudicated
observed_evidence cites frame/package and JSON keys
```

This proves report readiness, not judgment correctness. Do not add a test that
hard-codes a real workbook row as a VLM correctness oracle. If the user reports
a missed or wrong judgment, fix the shared cue/review contract and add a
contract/regression test for that class of miss.

## Evidence-Only Exception

Stop after evidence generation only when the user explicitly asks for
evidence-only output. Otherwise, normal workbook runs must produce and report
`llm_review_results.json`.
