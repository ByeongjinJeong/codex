# Regression Issue Type Instructions

This directory is the source of truth for Auto VLM feature judgment criteria.

When editing files here:

- Treat `od.md`, `ld.md`, `rbd.md`, `ts.md`, and `tl.md` as the active
  feature-specific tester guidance for Auto VLM.
- Put shared judgment rules in `common.md`.
- Put feature selection or rule-base interpretation policy in the existing
  support files instead of creating a parallel guideline directory.
- Preserve the distinction between evidence and judgment:
  raw/QV/JSON evidence must be inspected before applying these criteria.
- User feedback that changes future judging behavior should be incorporated
  into the relevant feature file with enough context for a junior ADAS vision
  tester to apply it later.
- Do not add final pass/fail conclusions for a specific run here. Run-specific
  judgments belong in `llm_review_results.json` under the run output directory.
