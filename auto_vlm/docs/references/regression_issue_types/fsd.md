# FSD Regression Issue Types

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

## 10. FSD: Freespace

Feature meaning:
- Freespace segment/range/azimuth/classification output.

### DEF-FSD-RANGE: FSD / Range or freespace value check

Definition:
- Freespace range/azimuth/classification value differs from expected range or criterion.

Key signals:
- `FSD_Range`
- `FSD_Azimuth_Angle`
- `FSD_Class`
- `FSD_Height`

Representative rule:
- `fsd.FSD_RANGE_CHECK`


