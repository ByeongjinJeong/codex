# Regression Issue Types Reference

This directory is the canonical Auto VLM evaluation-criteria source of truth for
regression feature and issue-type definitions.

Do not create a second feature-guideline tree elsewhere. If user feedback changes
how Auto VLM should judge OD, LD, RBD, TS, or TL, update the relevant file here
or add a support file in this directory.

Use it this way:

```text
focus_feature=OD
  common.md
  od.md

focus_feature=LD
  common.md
  ld.md

focus_feature=RBD
  common.md
  rbd.md

focus_feature=TS
  common.md
  ts.md

focus_feature=TL
  common.md
  tl.md

focus_feature=ALL
  common.md
  od.md
  ld.md
  rbd.md
  ts.md
  tl.md
```

Supporting files:

```text
rmd.md
fs_common.md
calib.md
cao.md
fsd.md
feature_selection_guide.md
rule_base_interpretation_guide.md
```

Policy:

```text
- These files are interpretation and classification guides, not GT.
- They must not be used to decide final pass/fail for a customer issue by themselves.
- VLM review must inspect FrameEvidencePackage evidence first, then use these files to classify observed symptoms.
- qualification_visualizer_output_info.md remains the QV/JSON interpretation guide.
- Run-specific judgments belong in outputs/<run_name>/llm_review_results.json, not in this directory.
```

Sync rule:

```text
The Korean aggregate file ../regression_feature_issue_type_definitions_ko.md remains the user-review source.
When it changes, update the matching Section IDs in these split English files.
```

