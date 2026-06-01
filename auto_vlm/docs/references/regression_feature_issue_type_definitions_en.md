# Regression Feature-Issue Type Definitions (EN)

This file is now an index. The canonical English reference content is split by feature under:

```text
docs/references/regression_issue_types/
```

Why split:

```text
- VLM feature review should load only the relevant issue vocabulary for the requested feature.
- OD, LD, RBD, TS, and TL reuse names like FN/FP, but each feature interprets them differently.
- Feature-scoped files are easier to maintain and safer for prompt construction.
```

Canonical files:

```text
regression_issue_types/README.md
regression_issue_types/common.md
regression_issue_types/od.md
regression_issue_types/ld.md
regression_issue_types/rbd.md
regression_issue_types/ts.md
regression_issue_types/tl.md
regression_issue_types/rmd.md
regression_issue_types/fs_common.md
regression_issue_types/calib.md
regression_issue_types/cao.md
regression_issue_types/fsd.md
regression_issue_types/feature_selection_guide.md
regression_issue_types/rule_base_interpretation_guide.md
```

Recommended VLM context loading:

```text
focus_feature=OD
  common.md + od.md

focus_feature=LD
  common.md + ld.md

focus_feature=RBD
  common.md + rbd.md

focus_feature=TS
  common.md + ts.md

focus_feature=TL
  common.md + tl.md

focus_feature=ALL
  common.md + od.md + ld.md + rbd.md + ts.md + tl.md
```

Reference usage policy:

```text
- qualification_visualizer_output_info.md is the QV/JSON interpretation guide.
- regression_issue_types/*.md files are feature/issue vocabulary guides.
- Neither reference source is ground truth.
- The VLM must inspect FrameEvidencePackage evidence before assigning feature or issue type.
```

Sync rule:

```text
The Korean file regression_feature_issue_type_definitions_ko.md remains the user-review source.
If the Korean file is edited, update the matching Section IDs in the split English files.
```
