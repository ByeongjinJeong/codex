# CALIB Regression Issue Types

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

## 8. CALIB: Calibration

Feature meaning:
- Camera calibration state, pose, progress, reason/status signal.

### DEF-CALIB-STATE: CALIB / State

Definition:
- Calibration state enum differs from expected state or remains wrong during timeout/OK conditions.

Representative rules:
- `cal.Calib_State`
- `cal.Calib_State_During_Cal_Timeout`

### DEF-CALIB-PROGRESS: CALIB / progress / state_progress_timesync

Definition:
- Calibration progress or time-sync related state progression differs from expected.

Representative rules:
- `cal.Calib_progress`
- `cal.Calib_state_progress_timesync`

### DEF-CALIB-POSE: CALIB / Pose

Definition:
- Calibration pose value is outside expected range.

Representative rule:
- `cal.Calib_Pose`

### DEF-CALIB-REASON: CALIB / reason_reset / paused reason / timeout reason

Definition:
- Calibration reason/status field does not reset after state transition, or differs from expected during timeout/paused conditions.

Representative rules:
- `cal.Error_reason_reset_at_Calib_OK`
- `cal.Calibrating_reason_reset_at_calib_OK`
- `cal.Calib_Paused_with_reason_radius`
- `cal.Calibrating_reason_at_Cal_Timeout`


