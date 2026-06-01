# FS And Common Regression Issue Types

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

## 7. FS / COMMON / OD_COMMON_HEADER

Feature meaning:
- Frame-level status, failsafe, common header, image quality/context signals.

### DEF-FS-DATA-UPDATE: FS / Data Update Failure

Definition:
- Failsafe or image-quality signal does not update as expected or remains invalid.

Example signals:
- `Blur_Image`
- `Full_Blockag`
- `Low_Sun`
- `Out_Of_Focus`
- `Sun_Ray`
- `Partial_Blockage`
- `Fog`
- `Rain`

Representative rule:
- `cmn.VALID_RANGE_CHECK_VALUE`

### DEF-COMMON-VALUE: COMMON / Valid value, all appear, attribute match, no object

Definition:
- Frame-level/common output must be inside valid range, must appear, must not appear, or must match expected attribute values.

Representative rules:
- `cmn.VALID_RANGE_CHECK_VALUE`
- `cmn.VALID_VALUE_APPEARS`
- `cmn.VALID_VALUES_ALL_APPEAR`
- `cmn.ATTRIBUTE_VALUES_MATCH`
- `cmn.NO_OBJECT_DETECTED`
- `cmn.REFERENCE_VALUE_RANGE`

### DEF-OD-HEADER: OD_COMMON_HEADER / Logging or common header check

Definition:
- OD common header or frame-level OD metadata should be logged/updated as expected.

Representative rule:
- `od.OD_COMMON_HEADER_LOGGING`


