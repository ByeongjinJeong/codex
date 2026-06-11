# Common Regression Issue Type Concepts

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

## 0. Overall Classification Model

```text
Feature
  The SW output domain being evaluated.
  Examples: OD, LD, RBD, TS, TL, RMD_SM, FS, CALIB.

Issue Type
  The symptom or defect mechanism inside that feature domain.
  Examples: FN, FP, Distance Long, Data Update Failure, Localization.

Method
  Evaluation mode.
  - Rule base: deterministic signal/range/jump/update/existence rule.
  - Reference: direct comparison against reference JSON / GT.

Rule Function
  Function executed for Rule base evaluation.
  Examples: od.OD_FN, ld.LD_RBD_FN, ts.TS_FN.
```

Interpretation model:
- Feature tells me which output group to inspect.
- Issue Type tells me which symptom pattern to focus on.
- Rule Function tells me how the tool tries to automate that symptom check.
- The same issue type name can mean different things by feature. For example, `FN` means missed object for OD, missed sign for TS, missed lane/road boundary for LD/RBD.

## 1. Common Issue Type Concepts

### DEF-COMMON-FN: FN / False Negative

Definition:
- A target that should exist, or exists in reference, is missing from the current SW output.

Feature-specific meaning:
- OD: vehicle/pedestrian/object should be present but no matching `OD` object exists.
- LD/RBD: expected lane or road boundary is missing.
- TS: expected traffic sign is missing.
- TL: expected traffic light is missing.
- CAO/RMD/etc.: expected feature object is missing.

Values to inspect:
- reference target existence
- current JSON feature list
- whether missing is continuous over the frame range
- track ID / lane role / bbox / long-lat position

Representative rules:
- `od.OD_FN`
- `ld.LD_RBD_FN`
- `ts.TS_FN`
- `cao.CAO_FN`

### DEF-COMMON-FP: FP / False Positive

Definition:
- A target that should not exist according to the real scene or reference appears in the current SW output.

Feature-specific meaning:
- OD: ghost or unnecessary object detection.
- LD/RBD: non-existent lane or road boundary is generated.
- TS/TL: sign/light output exists where no real/reference sign/light exists.
- RMD_SM: non-existent road marking is generated.

Values to inspect:
- whether current output matches reference
- whether bbox/position corresponds to a real object/mark
- whether multiple unnecessary outputs exist in the same area

Representative rules:
- `od.OD_FP`, `od.OD_FP_ver2`, `od.OD_FP_Type_Detected`
- `ld.LD_RBD_FP`
- `ts.TS_FP`, `ts.TSR_FP`, `ts.TS_FP_except_of_hit`
- `rmd.RMD_FP`

### DEF-COMMON-MISCLASS: Misclassification / Type Class / Class Check

Definition:
- The target is detected, but semantic label is wrong: class, type, state, shape, or sign name.

Feature-specific meaning:
- OD: object class is wrong, such as vehicle vs pedestrian.
- LD/RBD: lane/road boundary type class is wrong.
- TS: sign name, supplemental sign, or shape is wrong.
- TL: traffic light state/color/shape is wrong.

Values to inspect:
- whether the target is matched
- whether class/type/state field differs from expected
- whether this is semantic error rather than localization error

Representative rule/reference:
- `od.OD_Class_check`
- `ld.LD_RBD_TYPE_CLASS`
- TS reference issue types: `Misclassification`, `FN+Misclassification`, `Shape`
- TL reference issue types: `FN+Misclassification`

### DEF-COMMON-DISTANCE: Distance / Position Error

Definition:
- The target is detected, but its distance/position value is outside the expected range or changes abnormally across frames.

Key values:
- OD: `Dis_Long`, `Dis_Lat`
- TS/TL: `Long_Distance`, `Lat_Distance` family
- RMD: `SM_Long_Distance`, `SL_Long_Dist_*`, `SM_Lat_Distance`
- FSD: `FSD_Range`, `FSD_Azimuth_Angle`

Values to inspect:
- visual target location
- BEV/long-lat position
- difference from reference
- frame-to-frame delta

Representative rules:
- `od.OD_RANGE_VALIDITY`
- `od.OD_VALUE_JUMP`
- `ts.TS_LONG_DIST_ERROR_RANGE`
- `ts.TS_LONG_DIST_LINEARITY`
- `rmd.RMD_Distance_jump`
- `fsd.FSD_RANGE_CHECK`

### DEF-COMMON-UPDATE: Data Update Failure / Update Failure / Value Update Check

Definition:
- A target or frame-level signal exists, but a value does not update or stays at invalid/sentinel values.

Common invalid values:
- `0`
- `255`
- `3.4028234663852886e+38`
- `-3.4028234663852886e+38`
- `14683060830208.0`
- feature/rule-specific invalid enums

Values to inspect:
- whether the target exists but only a specific signal is frozen/invalid
- whether the scene requires the signal to change
- whether the signal alias exists in raw JSON/preprocessed output

Representative rules:
- `od.OD_Update_Failure`
- `ts.TS_Update_Failure`
- `ld.LD_RBD_Update`
- `rmd.RMD_Value_Update_Check`
- `cmn.VALID_RANGE_CHECK_VALUE`

### DEF-COMMON-JUMP: Value Jump / Flicker / Sudden Change

Definition:
- The same target or same feature signal changes abnormally between frames.

Values to inspect:
- whether comparison is on same track ID / same target
- frame-to-frame delta
- single-frame spike vs repeated flicker
- whether visual target actually changes abruptly

Representative rules:
- `od.OD_VALUE_JUMP`
- `od.OD_HEADING_ANGLE_JUMP`
- `ld.LD_CPP_VALUE_JUMP`
- `ts.TS_VALUE_JUMP`
- `rmd.RMD_Probability_jump`
- `rmd.RMD_Distance_jump`

### DEF-COMMON-ID: ID Switch / ID Duplication / ID Range / ID Consistency

Definition:
- Tracking ID does not stay stable for the same physical target, multiple IDs appear for one target, or ID changes abnormally.

Values to inspect:
- which IDs are assigned to the same physical target over the frame range
- whether the target disappears and reappears with a new ID
- whether multiple output IDs exist inside one reference target at the same time

Representative rules:
- `od.OD_ID_Switch`
- `od.OD_ID_Duplication`
- `ts.TS_VALUE_JUMP`
- `ts.TS_ID_CONSISTENCY`
- `rmd.RMD_ID_Update_Check`


