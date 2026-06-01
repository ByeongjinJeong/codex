# Feature Selection Guide

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

## 11. Feature Selection Guide

```text
Customer / Jira wording                Preferred Feature
---------------------------------------------------------
object, vehicle, pedestrian, bbox      OD
lane, lane line                        LD
road boundary, road edge               RBD
traffic sign, TSR, speed sign          TS
traffic light, TFL, signal light       TL
road marking, stop line                RMD_SM or RMD_SL
image quality, blur, blockage, sun     FS or COMMON
calibration, calib                     CALIB
construction area                      CAO or CAO_HEADER
freespace                              FSD
```

Notes:
- TSR usually maps to workbook feature `TS`.
- Road marking must be split into `RMD_SM` vs `RMD_SL`.
- Lane and road boundary must be split into `LD` vs `RBD`.
- Reference JSON may only be a target-matching aid; final method can still be `Rule base`.


