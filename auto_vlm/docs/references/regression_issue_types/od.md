# OD Regression Issue Types

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

## 2. OD: Object Detection

Feature meaning:
- Dynamic/static object detection output such as vehicles, pedestrians, VRU, and general objects.
- Key values: `Tracking_ID`, `Class`, `Dis_Long`, `Dis_Lat`, `Vel_Rel_Long`, `Vel_Rel_Lat`, `Vel_Abs_Long`, `Vel_Abs_Lat`, `Heading`, `Motion_Status`, bbox/image coordinates.

### DEF-OD-FN: OD / FN

Definition:
- A real/reference object should exist, but no matching OD output exists.

Review focus:
- reference object vs current object bbox/BEV matching.
- continuous missing vs partial missing across frame range.
- whether a class error makes it appear like FN.

Representative rule:
- `od.OD_FN`

### DEF-OD-FP: OD / FP

Definition:
- An object output is generated where no real/reference object should exist.

Review focus:
- ghost detection vs different real object compared to the wrong reference.
- output that fails bbox IoU or BEV IoU matching.

Representative rules:
- `od.OD_FP`
- `od.OD_FP_ver2`
- `od.OD_FP_Type_Detected`

### DEF-OD-BBOX-FIT: OD / Bounding box fit

Definition:
- Object is detected, but image bbox or projected 3D box does not fit the real object shape/location.

Review focus:
- whether bbox covers the target appropriately.
- whether front/rear/top/bottom projected corners align with the object in video.
- For `OD_large_bbox_candidates`, large image coverage is only a review cue. It is
  not a bbox-fit issue by itself when a near-field large vehicle/object naturally
  occupies a large part of the frame.
- Mark DEF-OD-BBOX-FIT only when raw/QV geometry visibly extends beyond, misses,
  or misaligns with the real object shape after considering near-field perspective
  and partial out-of-image cases.
- If the fit error comes from a rotated 3D projection or object orientation that
  disagrees with the vehicle's visible travel direction, also evaluate
  DEF-OD-HEADING. Do not collapse heading-angle errors into BBOX-FIT only.
- distinguish from pure distance error.

Representative rule:
- `od.OD_BOUNDING_BOX_FIT`

### DEF-OD-BBOX-DUP: OD / BBOX Duplication ICS/BEV

Definition:
- Two or more OD outputs are generated for the same real object or same location.

Split:
- `BBOX Duplication ICS`: image-space bbox duplication.
- `BBOX Duplication BEV`: BEV/world-space box duplication.

Review focus:
- whether two outputs indicate the same physical object.
- whether two different real objects naturally overlap.
- whether IDs are duplicated/split.
- For `OD_bbox_overlap_candidates`, inspect BEV/world-space placement before clearing
  the cue. ICS/image-space overlap is only a review cue, not sufficient evidence
  for duplication. BEV duplication is the stronger signal that two outputs occupy
  the same object/location.
- Clear the overlap candidate when the raw frame shows different physical objects,
  natural perspective overlap, or BEV/VCS separates the object locations.
- Do not clear BBOX duplication from ICS/image-space alone when BEV shows overlapping
  or split boxes for the same physical target.

Representative rule:
- `od.OD_ID_Duplication`
- duplication reference issue types

### DEF-OD-DIST-LONG: OD / Distance Long

Definition:
- Object longitudinal distance differs from real/reference expectation or is outside valid range.

Key signal:
- `Dis_Long`

Representative rules:
- `od.OD_RANGE_VALIDITY`
- `od.OD_VALUE_JUMP`

### DEF-OD-DIST-LAT: OD / Distance Lat / Distance Lat Lagging

Definition:
- Object lateral distance differs from real/reference expectation, or lags behind actual motion/lane change.

Key signal:
- `Dis_Lat`

Review focus:
- whether left/right position matches video/BEV.
- whether lateral value follows target motion late.

Representative rule/reference:
- `od.OD_RANGE_VALIDITY`
- `od.OD_LAT_DIST_INTO_HOST_PATH`

### DEF-OD-VELOCITY: OD / Velocity Abs/Rel Long/Lat

Definition:
- Object velocity output is outside expected range, inconsistent with actual motion, or jumps abnormally.

Key signals:
- `Vel_Rel_Long`
- `Vel_Rel_Lat`
- `Vel_Abs_Long`
- `Vel_Abs_Lat`

Representative rules:
- `od.OD_RANGE_VALIDITY`
- `od.OD_VALUE_JUMP`
- `od.OD_Update_Failure`

### DEF-OD-ACCEL: OD / Accel Abs Long/Lat

Definition:
- Object acceleration output is outside expected range or shows invalid/update failure.

Key signals:
- `Acc_Abs_Long`
- `Acc_Abs_Lat`

Representative rules:
- `od.OD_RANGE_VALIDITY`
- `od.OD_Update_Failure`
- combination issue types: `Accel Abs Long/Lat`, `Long Rel Vel+Abs Accel`

### DEF-OD-HEADING: OD / Heading Angle

Definition:
- Object heading/orientation value differs from actual direction or jumps abnormally across frames.

Key signal:
- `Heading`

Review focus:
- Compare the object's visible travel direction in the raw frame with the BEV/VCS
  orientation and JSON heading/orientation values.
- For a vehicle visibly driving straight with the lane or road direction, a BEV/VCS
  box rotated away from that direction is DEF-OD-HEADING even when the image bbox
  fit is also wrong.
- Keep DEF-OD-HEADING separate from DEF-OD-BBOX-FIT: fit describes whether the
  projected geometry matches the object shape; heading describes whether the
  object's orientation points the correct way.

Representative rules:
- `od.OD_RANGE_VALIDITY`
- `od.OD_HEADING_ANGLE_JUMP`

### DEF-OD-MOTION: OD / Motion Status

Definition:
- Object motion status/category does not match actual motion state or remains invalid.

Key signal:
- `Motion_Status`

Representative rules:
- `od.OD_Update_Failure`
- reference issue type: `Motion Status`

### DEF-OD-CLASS: OD / Class check / Misclassification

Definition:
- Object is detected, but class is wrong.

Review focus:
- vehicle/pedestrian/static category correctness.
- whether class error causes apparent FN/FP behavior.

Representative rule:
- `od.OD_Class_check`

### DEF-OD-ID: OD / ID Switching / ID Duplication

Definition:
- Tracking ID changes for the same object, or multiple IDs are generated for one object.

Key signal:
- `Tracking_ID`

Review focus:
- whether the same physical object keeps a stable tracking ID across the reviewed frame range.
- whether multiple object outputs share one real object or one object location.

Representative rules:
- `od.OD_ID_Switch`
- `od.OD_ID_Duplication`

### DEF-OD-DATA-UPDATE: OD / Data Update Failure

Definition:
- A specific object signal remains invalid/sentinel or fails to update.

Review focus:
- whether OD object fields remain at invalid/sentinel values.
- whether expected object attributes stop changing across frames despite visible scene changes.

Representative rule:
- `od.OD_Update_Failure`


