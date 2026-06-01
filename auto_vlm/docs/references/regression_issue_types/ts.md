# TS Regression Issue Types

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

## 4. TS: Traffic Sign

Feature meaning:
- Traffic sign recognition/sign tracking output.
- Key values: `Tracking_ID`, `Sign_Name`, `Sup1`, `Sup2`, `Sign_Shape`, `Long_Distance`, `Lat_Distance`, `Measurement_status`, `DBG_TOP/BOTTOM` bbox.

### DEF-TS-FN: TS / FN

Definition:
- Real/reference traffic sign should exist but is missing from output.

Review focus:
- whether a visible/reference traffic sign has no matching `traffic_signs[]` output.
- compare sign bbox, class, relevancy, and frame-range continuity.

Representative rule:
- `ts.TS_FN`

### DEF-TS-MISCLASS: TS / Misclassification / FN+Misclassification / Sup1

Definition:
- Sign is detected, but main sign or supplemental sign class is wrong.

Split:
- `Misclassification`: main sign class error.
- `Misclassification+Sup1`: includes supplemental sign error.
- `FN+Misclassification`: combined missing and wrong-class behavior across frames.
- `FN+Misclassification+Sup1`: missing plus main/supplemental class error.

Key values:
- `Sign_Name`, `Sup1`, `Sup2`, sign shape/class fields.

Representative reference issue types:
- `Misclassification`
- `FN+Misclassification`
- `FN+Misclassification+Sup1`
- `Misclassification+Sup1`

### DEF-TS-FP: TS / FP

Definition:
- Sign output is generated where no real/reference sign exists.

Review focus:
- whether `traffic_signs[]` output has no matching visible/reference sign.
- distinguish true sign detections from sign-like background/advertising objects.

Representative rules:
- `ts.TS_FP`
- `ts.TSR_FP`

### DEF-TS-FP-DUP: TS / FP Duplicate

Definition:
- Two or more valid traffic sign outputs are generated inside one reference sign bbox.

Review focus:
- whether duplicate sign IDs/bboxes describe the same physical sign.
- whether duplicate outputs persist or appear only from temporary overlap/occlusion.

Representative rule:
- `ts.TS_DUPLICATE_IN_REF_BBOX`

### DEF-TS-ID-RANGE: TS / ID Range

Definition:
- Sign tracking ID drops, changes, or reappears with a new ID within the frame range.

Key signal:
- `Tracking_ID`

Representative rules:
- `ts.TS_VALUE_JUMP` with `Tracking_ID`
- `ts.TS_ID_CONSISTENCY`

### DEF-TS-DIST-LONG: TS / Distance Long

Definition:
- Traffic sign longitudinal distance is outside expected range or differs too much within the same reference sign group.

Key signal:
- `Long_Distance`

Representative rules:
- `ts.TS_LONG_DIST_ERROR_RANGE`
- `ts.TS_LONG_DIST_LINEARITY`
- `ts.TS_SAME_REF_LONG_DIST_DIFF`

### DEF-TS-SHAPE: TS / Shape

Definition:
- Sign shape classification differs from expected.

Key signal:
- `Sign_Shape`

Representative reference issue type:
- `Shape`

### DEF-TS-MEASUREMENT: TS / Measurement_Status

Definition:
- Sign measurement status differs from expected or fails to update.

Key signal:
- `Measurement_status`

Representative rules:
- `ts.TS_Update_Failure`
- `ts.TS_VALUE_RANGE_CHECK`

### DEF-TS-AGE-IMAGE: TS / AGE CHECK / OUT_OF_IMAGE

Definition:
- Sign age is outside expected range, or in-image/out-of-image status is inconsistent with expectation.

Key values:
- age/count fields and in-image/out-of-image flags.

Representative rules:
- `ts.TS_AGE_CHECK`
- `ts.TS_OUT_OF_IMAGE_CHECK`


