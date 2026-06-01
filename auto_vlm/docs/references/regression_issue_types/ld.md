# LD Regression Issue Types

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

## LD Scope Note

Use this file when the review feature is `LD`.

Primary QV/JSON targets:
- `host_lanes[]`
- `adjacent_lanes[]`
- lane role/type, polynomial coefficients, range, confidence, existence, and drawing points

The original rule family is shared with RBD as `LD_RBD_*`, but the VLM review context should inspect lane-line evidence first when the focus feature is `LD`.

## 3. LD / RBD: Lane Detection / Road Boundary

Feature meaning:
- `LD`: lane line / host lane / adjacent lane.
- `RBD`: road boundary / road edge.
- Both share the same `LD_RBD_*` rule family.
- Key values: `Role`, `Type`, `C0`, `C1`, `C2`, `C3`, `Start`, `End`, `Range`, confidence/existence.

### DEF-LD-RBD-FN: LD/RBD / FN

Definition:
- Expected lane or road boundary is missing.

Review focus:
- for LD, whether visible host/adjacent lane lines are absent from `host_lanes[]` or `adjacent_lanes[]`.
- compare raw lane markings, QV overlay geometry, and JSON lane existence/range.

Representative rule:
- `ld.LD_RBD_FN`

### DEF-LD-RBD-FP: LD/RBD / FP

Definition:
- Lane or road boundary output is generated where it should not exist.

Review focus:
- whether lane overlay geometry appears on non-lane pixels or irrelevant structures.
- whether JSON lane elements have no matching visible lane-line evidence.

Representative rule:
- `ld.LD_RBD_FP`

### DEF-LD-RBD-RANGE: LD/RBD / Range

Definition:
- Recognition range of the lane/road boundary is too short/long or does not satisfy the required range condition.

Key values:
- `Start`, `End`, `Range`, lane drawing point extent, confidence/existence.

Representative rule:
- `ld.LD_RBD_RANGE`

### DEF-LD-RBD-LOCALIZATION: LD/RBD / Localization

Definition:
- Lane/road boundary is detected, but its location/curvature does not match actual or expected geometry.

Key values:
- `C1`, `C2`, `C3` or related polynomial coefficients.

Representative rule:
- `ld.LD_RBD_Localization`

### DEF-LD-RBD-CPP: LD/RBD / CPP

Definition:
- Path prediction / center path prediction polynomial output differs from expected geometry or is invalid.

Key values:
- `C0`, `C1`, `C2`, `C3`, `Start`, `End`

Representative rules:
- `ld.LD_RBD_CPP`
- `ld.LD_CPP_WITHIN_REF_LANES`
- `ld.LD_CPP_VALUE_JUMP`

### DEF-LD-RBD-COEFF: LD/RBD / C0, C1, C2, C1+C2

Definition:
- Lane/road boundary polynomial coefficient is outside expected range or changes abnormally.

Split:
- `C0`: lateral offset/position-like component.
- `C1`: heading/slope-like component.
- `C2`: curvature-like component.
- `C1+C2`: checks slope and curvature together.

Key values:
- `C0`, `C1`, `C2`, `C3`

Representative rules:
- `ld.LD_RBD_C0`
- `ld.LD_RBD_C1`
- `ld.LD_RBD_C2`
- `ld.LD_RBD_C1_C2`

### DEF-LD-RBD-TYPE: LD/RBD / Type class / Misclassification

Definition:
- Line is detected but lane/edge type class is wrong.

Review focus:
- whether solid/dashed/color/type output matches the visible lane marking.
- whether type enum changes contradict adjacent raw/QV evidence.

Representative rules:
- `ld.LD_RBD_TYPE_CLASS`
- `ld.LD_RBD_EnumMatch`

### DEF-LD-RBD-ROLE: LD/RBD / Role

Definition:
- Lane/road boundary role assignment is wrong.
- Example: left/right/host/adjacent/road-edge role confusion.

Review focus:
- whether left/right, host/adjacent, and lane/road-edge role assignment matches the visible road layout.
- for LD, do not accept road-edge-only evidence as lane evidence.

Representative rule:
- `ld.LD_RBD_Role`

### DEF-LD-RBD-UPDATE: LD/RBD / Update / Value_check / IS_EXIST

Definition:
- A specific lane/road boundary signal does not update, or required enum/value appearance/non-appearance condition is not satisfied.

Review focus:
- whether lane existence, type, role, coefficient, or confidence fields stay invalid/stale.
- whether required value appearance/non-appearance conditions match JSON and QV overlay.

Representative rules:
- `ld.LD_RBD_Update`
- `ld.LD_RBD_VAL_CHECK`
- `ld.LD_RBD_IS_EXIST`


