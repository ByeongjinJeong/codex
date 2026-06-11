# Rule Base Interpretation Guide

## Reference Metadata

Purpose:
- This file is part of the split English reference set for qualitative review of regression issues using `Regression_automation_tool` outputs.
- It explains what each feature and issue type means based on existing rules and workbook usage.
- It does not define the final pass/fail decision for a specific customer issue. Final judgment still requires issue text, video, raw JSON, preprocessed values, reference/filter JSON, frame range, and target ID/lane.

Sources inspected:
- Repo: `C:\Users\Byeongjin Jeong\Desktop\git\Regression_automation_tool`
- Main evidence:
  - `Input_Management_aptiv.xlsx` / `TC Management`
  - `Config/Config_tc_aptiv.py` / `tc_rules_mapping`
  - `Function Script/Rule_Function/*.py`
  - `Function Script/Evaluation_Reference.py`
  - `Config/Config_setting.py`

## 12. Rule Base Interpretation Guide

```text
Rule function pattern              Meaning
---------------------------------------------------------
*_FN                               target missing
*_FP                               extra/unwanted target
*_RANGE / *_VALIDITY               value in expected range
*_VALUE_JUMP                       abrupt frame-to-frame value change
*_Update_Failure                   failed update / invalid value persists
*_TYPE_CLASS / Class_check         semantic class/type error
*_ID_*                             tracking ID stability problem
*_BBOX_*                           image-space bbox position/duplication/fit problem
*_LOCALIZATION                     geometry/localization problem
*_CPP                              path prediction geometry problem
```

For qualitative review, do not conclude from the rule name alone.
- The rule name indicates the intended automated check.
- Actual interpretation must combine video, raw JSON, preprocessed values, reference/filter JSON, frame range, and target ID/lane.


