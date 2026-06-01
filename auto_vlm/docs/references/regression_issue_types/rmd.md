# RMD Regression Issue Types

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

## 6. RMD / RMD_SM / RMD_SL: Road Marking

Feature meaning:
- Road marking output.
- `RMD_SM`: symbol/marking object style.
- `RMD_SL`: stop line / line segment style.

### DEF-RMD-RANGE: RMD / RANGE_CHECK

Definition:
- Road marking related signal is outside expected range.

Representative rule:
- `rmd.RMD_RANGE_CHECK`

### DEF-RMD-UPDATE: RMD / Value_Update_Check

Definition:
- Road marking signal does not update or remains invalid.

Representative rule:
- `rmd.RMD_Value_Update_Check`

### DEF-RMD-FP: RMD_SM / FP

Definition:
- Non-existent road marking symbol/object is generated.

Representative rule:
- `rmd.RMD_FP`

### DEF-RMD-AGE-ID: RMD_SM / AGE CHECK / ID Update CHECK

Definition:
- Road marking age or ID does not persist/update as expected.

Representative rules:
- `rmd.RMD_AGE_CHECK`
- `rmd.RMD_ID_Update_Check`

### DEF-RMD-PROB-RES: RMD_SM / Probability_jump / Resolution Range

Definition:
- Road marking probability jumps or resolution-related value is outside expected range.

Representative rules:
- `rmd.RMD_Probability_jump`
- `rmd.RMD_Resolution_range`

### DEF-RMD-BBOX: RMD_SL / BBOX_Position

Definition:
- Road marking/stop line bbox or position differs from expected location.

Representative rule:
- `rmd.RMD_BBOX_Position`

### DEF-RMD-DIST-JUMP: RMD_SL / Distance_jump

Definition:
- Stop line / road marking distance value changes abruptly across frames.

Representative rule:
- `rmd.RMD_Distance_jump`


