# Project Map

This reference is for the `Regression_automation_tool` repository.

## Core Files

- `Execute_TC.py`
  - Runs enabled regression test cases from `TC Management`.
  - Default execution mode is `APTIV_Issue_Regression`.
  - `APTIV_Issue_Regression` maps to `Input_Management_aptiv.xlsx`.
  - CLI options can override execution mode and JSON1 base path:
    - `--excel_option`
    - `--json1_path`
    - `--json1_label`
  - Builds `TestCaseInfo` from rows starting at row 10.
  - Preloads `Reference Management` rows into `reference_data_map` by scenario ID.
  - Resolves JSON/video paths from workbook fixed cells and row-relative paths.
  - Calls `Pre_process_parse_match.func_parse_and_match(tc_info)`, then `Handle_test_method.switch_method(...)`, then writes report sheets.
- `Extract_Reference.py`
  - Generates filtered reference JSON data from `Reference Management`.
  - Processes rows whose status is `NOT READY`, then marks them `READY`.
  - Default execution mode is `APTIV_Issue_Regression`.
  - For APTIV, reads `Input_Management_aptiv.xlsx` and writes references under `\\10.20.20.230\nqa\Project\APTIV\04_Tool\Reference_GT_customer`.
  - Creates output under `<reference_output_path>/<issue_id>/filter_json`, with feature-specific `OD_json` or `LD_json` subfolders when the source has those folders.
  - Reads raw JSONs from the row `JSON PATH` and filters/overrides object content based on feature, frame range, track ID, optional value, and optional criteria.
- `Input_Management_aptiv.xlsx`
  - Main APTIV customer issue regression workbook.
- `Issue_Request_aptiv.xlsx`
  - Codex request queue workbook for user-supplied issue additions.
  - Sheet: `Issue Queue`.
  - Codex processes rows with `STATUS = 이슈추가`.
  - Supports `검토요청` / `prepare only` analysis-only mode.
  - Codex writes `CODEX_RESULT`, `CODEX_ANALYSIS_LOG`, and `UPDATED_AT`.
- `Config/Config_tc_aptiv.py`
  - Contains `tc_rules_mapping` for APTIV Rule base scenarios.
  - Rule entries use:
    - single rule: `'FXE-xxxx': ['module.FUNCTION', criteria]`
    - combination rule: `'FXE-xxxx': [['module.FUNCTION', criteria], ...]`
  - Rule module prefixes observed:
    - `od`: object detection rules
    - `ld`: lane / road boundary rules
    - `ts`: traffic sign rules
    - plus imported common/calibration/CAO/RMD/FSD modules in evaluation code
- `Function Script/Handle_test_method.py`
  - Dispatches `Rule base` to `Evaluation_Rule`.
  - Dispatches `Reference` to `Evaluation_Reference`.
  - Runs `Pre_process_sort_attribute.update_value_name(...)` before method dispatch.
  - Applies heading smoothing before rule/reference evaluation.
  - Plots result graphs when comparing more than one JSON.
- `Function Script/Evaluation_Rule.py`
  - Loads `Config_tc_aptiv.tc_rules_mapping` for `APTIV_Issue_Regression`.
  - Selects mapping by `tc_info.execution_type`:
    - `APTIV_Internal_Test` -> `Config_tc_internal.tc_rules_mapping`
    - `APTIV_Issue_Regression` -> `Config_tc_aptiv.tc_rules_mapping`
    - `Common_Issue_Regression` -> `Config_tc_common.tc_rules_mapping`
  - If no scenario mapping exists, marks the scenario as `Not Tested`.
  - Supports single rule and combination rule configs.
- `Function Script/Evaluation_Reference.py`
  - Dispatches reference-based checks by feature and issue type.
  - Feature dispatch:
    - `OD` -> OD issue dispatch table
    - `LD` / `RBD` -> lane / road boundary issue dispatch table
    - `TS` -> traffic sign issue dispatch table
    - `TL` -> traffic light issue dispatch table
  - Unsupported feature or issue type becomes `Not Tested`.
- `Config/Config_setting.py`
  - Shared interface/signal/config mappings.
  - Contains AVI and COMMON interface mappings for OD, LD/RBD, TS, TL, and RMD.
  - Contains output templates and evaluation thresholds used by reference/rule functions.

## Rule And Reference Function Areas

Rule files:

- `Function Script/Rule_Function/Rule_OD.py`
- `Function Script/Rule_Function/Rule_LD_RBD.py`
- `Function Script/Rule_Function/Rule_TS.py`
- `Function Script/Rule_Function/Rule_Common.py`
- `Function Script/Rule_Function/Rule_Calibration.py`
- `Function Script/Rule_Function/Rule_CAO.py`
- `Function Script/Rule_Function/Rule_RMD.py`
- `Function Script/Rule_Function/Rule_FSD.py`
- `Function Script/Rule_Function/Rule_Base.py`

Reference files:

- `Function Script/Reference_Function/Ref_OD.py`
- `Function Script/Reference_Function/Ref_LD_RBD.py`
- `Function Script/Reference_Function/Ref_TS.py`
- `Function Script/Reference_Function/Ref_TL.py`

Reference issue types currently dispatched:

- OD:
  - `BBOX Duplication ICS`
  - `BBOX Duplication BEV`
  - `Data Update Failure`
  - `FN`
  - `FP`
  - `Heading Angle`
  - `Distance Long`
  - `Distance Lat`
  - `Distance Lat Lagging`
  - `Velocity Abs Long`
  - `Velocity Rel Long`
  - `Velocity Rel Lat`
  - `Accel Abs Long`
  - `Long Dis+Rel Vel`
  - `Long Dis+Abs Vel`
  - `Accel Abs Long/Lat`
  - `Long Rel Vel+Abs Accel`
  - `Long Dis+Heading`
  - `Motion Status`
- LD/RBD:
  - `FN`
  - `FP`
  - `Range`
  - `Type class`
  - `C0`
- TS:
  - `FN+Misclassification`
  - `FN+Misclassification+Sup1`
  - `Misclassification`
  - `FN`
  - `Shape`
  - `Misclassification+Sup1`
- TL:
  - `FN+Misclassification`
  - `FN`

## Excel Workbook

Workbook: `Input_Management_aptiv.xlsx`

Observed sheets:

- `TC Management`
- `Reference Management`
- `TEMP2`
- `TEMP`
- `NOTE`

### TC Management

Execution starts at row 10 in `Execute_TC.py`.

Header row is row 9. Data rows begin at row 10.

Important row fields consumed by `TestCaseInfo`:

- A: enabled
- B: scenario / issue ID
- C: method
- D: feature
- E: issue type
- F: reference path
- G: JSON1 path
- H: JSON2 path
- I: video1 path
- J: video2 path
- K: ticket status
- L: business value
- M: issue title
- O:S: data attributes 1-5

Fixed cells used during execution:

- I4: JSON1 Coco6 parent path
- C5: JSON2 option
- C6: MBLY option
- F5: JSON1 name
- F6: JSON2 name
- I5: JSON2 Coco6 parent path
- I6: report template

Only rows with enabled truthy values run. Rows marked `Manual` are skipped but included in summary. `No Dataset` rows with no JSON are skipped.

### Reference Management

Reference extraction starts at row 6 in `Extract_Reference.py`.

Header row is row 5. Data rows begin at row 6.

Important columns:

- A: status
- B: issue ID
- C: feature type
- D: start frame
- E: end frame
- F: track ID or lane
- G: base SW version
- H: video file name
- I: JSON path
- J: optional value name
- K: optional criteria value
- M: note

`Extract_Reference.py` processes rows only when status is `NOT READY` and required data is present. Rows with status `READY` are considered already generated.

Feature-specific reference extraction behavior:

- `OD`, `TS`, `TL`, `RMD_SM`, `RMD_SL` track IDs are numeric or `ALL`.
- `LD` / `RBD` track IDs are lane position strings such as `L`, `R`, `LL`, `RR`, `L1`, `R1`.
- Optional value can request special overrides such as `DGPS`, `Radar`, `Lidar`, or feature attribute values.
- Optional criteria holds the override value or external ID list needed by the optional value.

## Current Known Example

Existing current working tree includes user edits for:

- `FXE-1509`
- `FXE-1510`

Observed rule mappings added:

```python
'FXE-1509' : ['ts.TS_VALUE_JUMP', (0.5, 'Tracking_ID', 'Traffic Sign tracking ID')],
'FXE-1510' : ['ts.TS_FN', None],
```

Observed TC rows:

- `FXE-1509`
  - enabled: `TRUE`
  - method: `Rule base`
  - feature: `TS`
  - issue type: `ID Range`
  - reference path: `\\10.20.20.230\nqa\Project\APTIV\04_Tool\Reference_GT_customer\FXE-1509\filter_json`
  - JSON1 row path: `APTIV_KTC\FXE_1509_1510\20250924_143027_0033\SV_INSPECTOR_json`
  - video1 row path: `APTIV_KTC\FXE_1509_1510\20250924_143027_0033\ThunderMCIP_WS11656_20250924_143027_0033_FLC_cam_1.mp4`
  - ticket status: `IDENTIFIED`
  - business value: `5`
  - title: `[TSR] Dropped classified SL sign is detected again with a new id`
  - resolution: `3MP`
  - attribute 1: `Tracking_ID`
- `FXE-1510`
  - enabled: `TRUE`
  - method: `Rule base`
  - feature: `TS`
  - issue type: `FN`
  - same JSON/video paths as `FXE-1509`
  - title: `[TSR] Traffic sign is not tracked when leaving field of view`
  - attribute 1: `Tracking_ID`

Observed Reference Management rows:

- `FXE-1509`
  - status: `READY`
  - feature type: `TS`
  - frame range: `300` to `340`
  - track ID: `10`
  - base SW: `RC23.00.00.88 PC`
  - video file name: `ThunderMCIP_WS11656_20250924_143027_0033_FLC_cam_1`
  - JSON path: `\\10.20.20.224\root_share\home\qaci\qatest\LOCAL_RESULT\APTIV\APTIVCEER-RC23.00.00.88_QT_01_Regression\APTIV_KTC\FXE_1509_1510\20250924_143027_0033\SV_INSPECTOR_json`
- `FXE-1510`
  - same reference setup as `FXE-1509`

## Issue Request Workbook

Workbook: `Issue_Request_aptiv.xlsx`

Observed sheets:

- `Issue Queue`

Header row is row 1. Request rows begin at row 2.

Columns:

- A: `STATUS`
- B: `ISSUE_ID`
- C: `JIRA_TICKET`
- D: `USER_HINT`
- E: `FRAME_START`
- F: `FRAME_END`
- G: `TRACK_ID_OR_LANE`
- H: `JSON_PATH`
- I: `VIDEO_PATH`
- J: `NOTES`
- K: `CODEX_RESULT`
- L: `CODEX_ANALYSIS_LOG`
- M: `UPDATED_AT`

Status values:

- `이슈추가`: process row.
- `검토중`: blocked or in-progress; see `CODEX_RESULT`.
- `검토요청`: prepare analysis/proposed changes only.
- `완료`: processed.
- `보류`: intentionally deferred.
- `오류`: failed.

Column ownership colors:

- `STATUS`: shared status column.
- `ISSUE_ID` through `NOTES`: user input columns.
- `CODEX_RESULT` through `UPDATED_AT`: Codex output columns.
