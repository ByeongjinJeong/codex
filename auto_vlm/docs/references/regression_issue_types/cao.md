# CAO Regression Issue Types

## Reference Metadata

Purpose:
- This file is part of the split English reference set for qualitative review of regression issues using `Regression_automation_tool` outputs.
- It explains what each feature and issue type means based on existing rules and workbook usage.
- It does not define the final pass/fail decision for a specific customer issue. Final judgment still requires issue text, video, raw JSON, preprocessed values, reference/filter JSON, frame range, and target ID/lane.

Sync rule:
- The Korean file `../regression_feature_issue_type_definitions_ko.md` remains the user-review source.
- If the Korean file is edited, update the matching Section IDs in this split English reference set.
- The index file `../regression_feature_issue_type_definitions_en.md` points to these canonical split English files.

Sources inspected:
- Repo: `C:\Users\Byeongjin Jeong\Desktop\git\Regression_automation_tool`
- Main evidence:
  - `Input_Management_aptiv.xlsx` / `TC Management`
  - `Config/Config_tc_aptiv.py` / `tc_rules_mapping`
  - `Function Script/Rule_Function/*.py`
  - `Function Script/Evaluation_Reference.py`
  - `Config/Config_setting.py`

## 9. CAO / CAO_HEADER: Construction Area Object

Feature meaning:
- Construction area object or construction area header/flag output.

### DEF-CAO-FN: CAO / FN

Definition:
- Construction area object/header should exist but is missing.

Representative rules:
- `cao.CAO_FN`
- `cao.CAO_Construction_Area_Flag`

### DEF-CAO-BBOX: CAO / BBOX Localization ICS

Definition:
- Construction area object image-space bbox location differs from expected location.

Representative rule:
- `cao.CAO_BBOX_Localization_ICS`


