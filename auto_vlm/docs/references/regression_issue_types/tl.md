# TL Regression Issue Types

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

## 5. TL: Traffic Light

Feature meaning:
- Traffic light detection/state/spot output.
- Key values: `Tracking_ID`, `Long_Distance`, `Spot_Color`, `Spot_Shape`, state/sequence, debug bbox.

### DEF-TL-FN: TL / FN

Definition:
- Real/reference traffic light should exist but is missing from output.

Review focus:
- whether a visible/reference traffic light has no matching `traffic_lights[]` output.
- compare raw light structure, QV bbox/state overlay, and JSON light existence.

Representative reference issue type:
- `FN`

### DEF-TL-FP: TL / FP

Definition:
- Traffic light output is generated where no real/reference traffic light exists.

Review focus:
- reference bbox vs current TL bbox matching.
- if using a virtual reference such as an OD object rear face, confirm reference creation semantics.

### DEF-TL-DIST-LONG: TL / Distance Long

Definition:
- Traffic light longitudinal distance differs from expected range.

Key signal:
- `Long_Distance`

### DEF-TL-STATE: TL / State sequence

Definition:
- Traffic light state transition sequence differs from expected sequence.

Key values:
- state/sequence fields and frame-to-frame transition order.

### DEF-TL-SPOT: TL / Spot color/shape

Definition:
- Traffic light spot color or shape enum differs from expected.

Key values:
- `Spot_Color`
- `Spot_Shape`

Representative rules:
- `tl.TL_Signal_Comparison`
- `cmn.ATTRIBUTE_VALUES_MATCH`


