# Regression Feature-Issue Type 정의서 (KO)

목적:
- `Regression_automation_tool`의 기존 rule / workbook 분류를 기준으로, 내가 나중에 영상+JSON을 보고 정성평가할 때 feature와 issue type의 의미를 헷갈리지 않도록 정리한다.
- 이 문서는 "어떤 현상을 어떤 feature-issue type으로 이해할지"에 대한 의미 정의다.
- 특정 고객 이슈의 최종 판정 기준, threshold, pass/fail 결론은 별도 이슈 정보와 실제 JSON/영상 확인 후 결정한다.

동기화 규칙:
- 이 한글 문서를 사용자가 수정하면, 같은 Section ID를 가진 영어 문서 `regression_feature_issue_type_definitions_en.md`에 반영한다.
- 영어 문서는 나중에 내가 사용할 작업본이고, 한글 문서는 사용자 검토/수정용 원본이다.

조사 기준:
- Repo: `C:\Users\Byeongjin Jeong\Desktop\git\Regression_automation_tool`
- 주요 근거:
  - `Input_Management_aptiv.xlsx` / `TC Management`
  - `Config/Config_tc_aptiv.py` / `tc_rules_mapping`
  - `Function Script/Rule_Function/*.py`
  - `Function Script/Evaluation_Reference.py`
  - `Config/Config_setting.py`

## 0. 전체 분류 구조

```text
Feature
  SW output의 기능 영역.
  예: OD, LD, RBD, TS, TL, RMD_SM, FS, CALIB 등.

Issue Type
  그 기능 영역에서 고객이 본 증상 또는 검증하려는 결함 유형.
  예: FN, FP, Distance Long, Data Update Failure, Localization 등.

Method
  평가 방식.
  - Rule base: 특정 signal, range, jump, update, existence 조건을 rule로 판단.
  - Reference: reference JSON/GT와 현재 JSON을 직접 비교.

Rule Function
  Rule base 평가에서 실제로 실행되는 함수.
  예: od.OD_FN, ld.LD_RBD_FN, ts.TS_FN.
```

정성평가할 때의 기본 독해:
- Feature는 "어떤 output group을 봐야 하는가"를 정한다.
- Issue Type은 "그 output group에서 어떤 현상에 집중해야 하는가"를 정한다.
- Rule Function은 "툴이 그 현상을 어떻게 자동 검증하려고 설계되어 있는가"를 보여준다.
- 같은 issue type 이름이라도 feature가 다르면 의미가 달라진다. 예를 들어 `FN`은 OD에서는 object 미검출, TS에서는 표지판 미검출, LD/RBD에서는 lane/road boundary 미검출이다.

## 1. 공통 Issue Type 개념

### DEF-COMMON-FN: FN / False Negative

정의:
- 실제로 존재하거나 reference에 있는 target이 현재 SW output에서 누락되는 현상.

Feature별 의미:
- OD: 차량/보행자/객체가 있어야 하는데 `OD` object가 없음.
- LD/RBD: lane 또는 road boundary가 있어야 하는데 해당 line feature가 없음.
- TS: traffic sign이 있어야 하는데 sign output이 없음.
- TL: traffic light가 있어야 하는데 light output이 없음.
- CAO/RMD 등: 해당 feature object가 있어야 하는데 output이 없음.

정성평가 시 보는 값:
- reference target 존재 여부
- current JSON의 해당 feature list
- frame range 내 지속 누락 여부
- track ID / lane role / bbox / long-lat 위치

대표 rule:
- `od.OD_FN`
- `ld.LD_RBD_FN`
- `ts.TS_FN`
- `cao.CAO_FN`

### DEF-COMMON-FP: FP / False Positive

정의:
- 실제 또는 reference 기준으로 없어야 하는 target이 현재 SW output에 생성되는 현상.

Feature별 의미:
- OD: ghost object 또는 불필요한 object detection.
- LD/RBD: 존재하지 않는 lane/road boundary가 생성됨.
- TS/TL: 실제 표지판/신호등이 아닌데 output이 생성됨.
- RMD_SM: 없는 road marking이 생성됨.

정성평가 시 보는 값:
- current output이 reference와 매칭되는지
- bbox/position이 실제 물체나 표시와 맞는지
- 동일 영역에 불필요한 중복 output이 있는지

대표 rule:
- `od.OD_FP`, `od.OD_FP_ver2`, `od.OD_FP_Type_Detected`
- `ld.LD_RBD_FP`
- `ts.TS_FP`, `ts.TSR_FP`, `ts.TS_FP_except_of_hit`
- `rmd.RMD_FP`

### DEF-COMMON-MISCLASS: Misclassification / Type Class / Class Check

정의:
- target은 검출되었지만 class/type/state/shape/sign name 같은 semantic label이 잘못된 현상.

Feature별 의미:
- OD: object class가 vehicle/pedestrian 등 실제와 다름.
- LD/RBD: lane/road boundary type class가 다름.
- TS: sign name, supplemental sign, shape가 다름.
- TL: light state/color/shape가 다름.

정성평가 시 보는 값:
- target matching은 되었는가
- class/type/state field가 기대값과 다른가
- 단순 위치 오차인지 semantic label 오류인지 분리

대표 rule/reference:
- `od.OD_Class_check`
- `ld.LD_RBD_TYPE_CLASS`
- TS reference issue types: `Misclassification`, `FN+Misclassification`, `Shape`
- TL reference issue types: `FN+Misclassification`

### DEF-COMMON-DISTANCE: Distance / Position Error

정의:
- target은 검출되었지만 거리/위치 값이 기대 범위와 다르거나 frame 간 비정상적으로 변화하는 현상.

주요 값:
- OD: `Dis_Long`, `Dis_Lat`
- TS/TL: `Long_Distance`, `Lat_Distance` 계열
- RMD: `SM_Long_Distance`, `SL_Long_Dist_*`, `SM_Lat_Distance`
- FSD: `FSD_Range`, `FSD_Azimuth_Angle`

정성평가 시 보는 값:
- 영상상 target 위치
- BEV/long-lat 위치
- reference 대비 차이
- frame-to-frame 변화량

대표 rule:
- `od.OD_RANGE_VALIDITY`
- `od.OD_VALUE_JUMP`
- `ts.TS_LONG_DIST_ERROR_RANGE`
- `ts.TS_LONG_DIST_LINEARITY`
- `rmd.RMD_Distance_jump`
- `fsd.FSD_RANGE_CHECK`

### DEF-COMMON-UPDATE: Data Update Failure / Update Failure / Value Update Check

정의:
- target 또는 frame-level signal이 존재하지만 값이 갱신되지 않거나 invalid/sentinel 값으로 유지되는 현상.

자주 나오는 invalid 값:
- `0`
- `255`
- `3.4028234663852886e+38`
- `-3.4028234663852886e+38`
- `14683060830208.0`
- feature/rule별 별도 invalid enum

정성평가 시 보는 값:
- target은 있는데 특정 signal만 고정/invalid인지
- frame range 동안 값이 변해야 하는 상황인지
- signal alias가 실제 JSON/preprocessed output에 존재하는지

대표 rule:
- `od.OD_Update_Failure`
- `ts.TS_Update_Failure`
- `ld.LD_RBD_Update`
- `rmd.RMD_Value_Update_Check`
- `cmn.VALID_RANGE_CHECK_VALUE`

### DEF-COMMON-JUMP: Value Jump / Flicker / Sudden Change

정의:
- 같은 target 또는 같은 feature signal이 frame 간 비정상적으로 크게 튀는 현상.

정성평가 시 보는 값:
- 같은 track ID / same target 기준인지
- frame 간 변화량
- 단발 jump인지 반복 flicker인지
- 영상상 target이 실제로 급변했는지

대표 rule:
- `od.OD_VALUE_JUMP`
- `od.OD_HEADING_ANGLE_JUMP`
- `ld.LD_CPP_VALUE_JUMP`
- `ts.TS_VALUE_JUMP`
- `rmd.RMD_Probability_jump`
- `rmd.RMD_Distance_jump`

### DEF-COMMON-ID: ID Switch / ID Duplication / ID Range / ID Consistency

정의:
- tracking ID가 같은 물체를 안정적으로 따라가지 못하거나, 하나의 target에 여러 ID가 생기거나, ID가 비정상적으로 바뀌는 현상.

정성평가 시 보는 값:
- 같은 물리 target이 frame range 동안 어떤 ID로 유지되는지
- ID가 끊겼다가 새 ID로 재검출되는지
- 하나의 reference target 안에 여러 output ID가 동시에 존재하는지

대표 rule:
- `od.OD_ID_Switch`
- `od.OD_ID_Duplication`
- `ts.TS_VALUE_JUMP`
- `ts.TS_ID_CONSISTENCY`
- `rmd.RMD_ID_Update_Check`

## 2. OD: Object Detection

Feature 의미:
- 차량, 보행자, VRU, 일반 object 등 동적/정적 object detection output.
- 주요 값: `Tracking_ID`, `Class`, `Dis_Long`, `Dis_Lat`, `Vel_Rel_Long`, `Vel_Rel_Lat`, `Vel_Abs_Long`, `Vel_Abs_Lat`, `Heading`, `Motion_Status`, bbox/image coordinate.

### DEF-OD-FN: OD / FN

정의:
- 실제 object 또는 reference object가 있어야 하는데 현재 OD output에 매칭되는 object가 없음.

평가 관점:
- reference object와 current object의 bbox/BEV 매칭 여부.
- frame range 동안 계속 누락인지, 일부 frame만 누락인지.
- object class가 달라서 FN처럼 보이는지 별도 확인.

대표 rule:
- `od.OD_FN`

### DEF-OD-FP: OD / FP

정의:
- 실제 또는 reference 기준으로 없어야 하는 object가 현재 OD output에 생성됨.

평가 관점:
- ghost detection인지, 다른 실제 물체를 잘못 reference와 비교한 것인지.
- bbox IoU 또는 BEV IoU 기준으로 매칭 실패하는 output인지.

대표 rule:
- `od.OD_FP`
- `od.OD_FP_ver2`
- `od.OD_FP_Type_Detected`

### DEF-OD-BBOX-FIT: OD / Bounding box fit

정의:
- object는 검출되었지만 image bbox 또는 3D projected box가 실제 object 외형과 잘 맞지 않는 현상.

평가 관점:
- bbox가 target 전체를 적절히 감싸는지.
- 앞/뒤/상/하 corner projection이 영상상 물체 위치와 맞는지.
- 단순 distance 오차와 구분.

대표 rule:
- `od.OD_BOUNDING_BOX_FIT`

### DEF-OD-BBOX-DUP: OD / BBOX Duplication ICS/BEV

정의:
- 동일한 실제 object 또는 동일 위치에 둘 이상의 OD output이 중복 생성되는 현상.

구분:
- `BBOX Duplication ICS`: image-space bbox 중복.
- `BBOX Duplication BEV`: BEV/world position box 중복.

평가 관점:
- 두 output이 같은 물체를 가리키는지.
- 서로 다른 실제 물체인데 bbox가 겹치는 정상 상황인지.
- ID도 중복/분리되는지.

대표 rule:
- `od.OD_ID_Duplication`
- 중복 관련 reference issue type

### DEF-OD-DIST-LONG: OD / Distance Long

정의:
- object의 longitudinal distance가 실제/reference 기대와 다르거나 유효 범위를 벗어나는 현상.

주요 signal:
- `Dis_Long`

대표 rule:
- `od.OD_RANGE_VALIDITY`
- `od.OD_VALUE_JUMP`

### DEF-OD-DIST-LAT: OD / Distance Lat / Distance Lat Lagging

정의:
- object의 lateral distance가 실제/reference 기대와 다르거나, 움직임/차선 변화 대비 지연되는 현상.

주요 signal:
- `Dis_Lat`

평가 관점:
- 좌우 위치가 영상/BEV와 맞는지.
- target이 움직이는데 lateral value가 늦게 따라오는지.

대표 rule/reference:
- `od.OD_RANGE_VALIDITY`
- `od.OD_LAT_DIST_INTO_HOST_PATH`

### DEF-OD-VELOCITY: OD / Velocity Abs/Rel Long/Lat

정의:
- object velocity output이 실제 움직임이나 reference 기대 범위와 다르거나 갑자기 튀는 현상.

주요 signal:
- `Vel_Rel_Long`
- `Vel_Rel_Lat`
- `Vel_Abs_Long`
- `Vel_Abs_Lat`

대표 rule:
- `od.OD_RANGE_VALIDITY`
- `od.OD_VALUE_JUMP`
- `od.OD_Update_Failure`

### DEF-OD-ACCEL: OD / Accel Abs Long/Lat

정의:
- object acceleration output이 기대 범위를 벗어나거나 invalid/update failure를 보이는 현상.

주요 signal:
- `Acc_Abs_Long`
- `Acc_Abs_Lat`

대표 rule:
- `od.OD_RANGE_VALIDITY`
- `od.OD_Update_Failure`
- combination issue types: `Accel Abs Long/Lat`, `Long Rel Vel+Abs Accel`

### DEF-OD-HEADING: OD / Heading Angle

정의:
- object heading/orientation 값이 실제 방향과 다르거나 frame 간 비정상적으로 jump하는 현상.

주요 signal:
- `Heading`

대표 rule:
- `od.OD_RANGE_VALIDITY`
- `od.OD_HEADING_ANGLE_JUMP`

### DEF-OD-MOTION: OD / Motion Status

정의:
- object의 motion status/category가 실제 움직임 상태와 다르거나 invalid 상태인 현상.

주요 signal:
- `Motion_Status`

대표 rule:
- `od.OD_Update_Failure`
- reference issue type: `Motion Status`

### DEF-OD-CLASS: OD / Class check / Misclassification

정의:
- object가 검출되었지만 class가 실제와 다름.

평가 관점:
- vehicle/pedestrian/static 등 category가 맞는지.
- class 오류 때문에 FN/FP처럼 보이는지.

대표 rule:
- `od.OD_Class_check`

### DEF-OD-ID: OD / ID Switching / ID Duplication

정의:
- 같은 object의 tracking ID가 바뀌거나, 하나의 object에 여러 ID가 중복 생성되는 현상.

대표 rule:
- `od.OD_ID_Switch`
- `od.OD_ID_Duplication`

### DEF-OD-DATA-UPDATE: OD / Data Update Failure

정의:
- object의 특정 signal이 invalid/sentinel 값으로 유지되거나 갱신되지 않는 현상.

대표 rule:
- `od.OD_Update_Failure`

## 3. LD / RBD: Lane Detection / Road Boundary

Feature 의미:
- `LD`: lane line / host lane / adjacent lane.
- `RBD`: road boundary / road edge.
- 두 feature가 같은 rule family `LD_RBD_*`를 공유한다.
- 주요 값: `Role`, `Type`, `C0`, `C1`, `C2`, `C3`, `Start`, `End`, `Range`, confidence/existence.

### DEF-LD-RBD-FN: LD/RBD / FN

정의:
- 있어야 하는 lane 또는 road boundary가 output에 없음.

대표 rule:
- `ld.LD_RBD_FN`

### DEF-LD-RBD-FP: LD/RBD / FP

정의:
- 없어야 하는 lane 또는 road boundary가 output에 생성됨.

대표 rule:
- `ld.LD_RBD_FP`

### DEF-LD-RBD-RANGE: LD/RBD / Range

정의:
- lane/road boundary의 인식 range가 너무 짧거나 길이 조건을 만족하지 못하는 현상.

대표 rule:
- `ld.LD_RBD_RANGE`

### DEF-LD-RBD-LOCALIZATION: LD/RBD / Localization

정의:
- lane/road boundary는 검출되었지만 위치/곡률이 실제 또는 기대 geometry와 다름.

주요 값:
- `C1`, `C2`, `C3` 또는 관련 polynomial coefficient.

대표 rule:
- `ld.LD_RBD_Localization`

### DEF-LD-RBD-CPP: LD/RBD / CPP

정의:
- path prediction / center path prediction 계열의 polynomial output이 기대 geometry와 다르거나 invalid한 현상.

주요 값:
- `C0`, `C1`, `C2`, `C3`, `Start`, `End`

대표 rule:
- `ld.LD_RBD_CPP`
- `ld.LD_CPP_WITHIN_REF_LANES`
- `ld.LD_CPP_VALUE_JUMP`

### DEF-LD-RBD-COEFF: LD/RBD / C0, C1, C2, C1+C2

정의:
- lane/road boundary polynomial coefficient가 기대 범위와 다르거나 비정상적으로 튀는 현상.

구분:
- `C0`: lateral offset/position 계열.
- `C1`: heading/slope 계열.
- `C2`: curvature 계열.
- `C1+C2`: slope와 curvature를 동시에 보는 경우.

대표 rule:
- `ld.LD_RBD_C0`
- `ld.LD_RBD_C1`
- `ld.LD_RBD_C2`
- `ld.LD_RBD_C1_C2`

### DEF-LD-RBD-TYPE: LD/RBD / Type class / Misclassification

정의:
- line은 검출되었지만 lane/edge type class가 기대와 다름.

대표 rule:
- `ld.LD_RBD_TYPE_CLASS`
- `ld.LD_RBD_EnumMatch`

### DEF-LD-RBD-ROLE: LD/RBD / Role

정의:
- lane/road boundary의 role이 잘못 할당되는 현상.
- 예: left/right/host/adjacent/road edge 역할 혼동.

대표 rule:
- `ld.LD_RBD_Role`

### DEF-LD-RBD-UPDATE: LD/RBD / Update / Value_check / IS_EXIST

정의:
- lane/road boundary의 특정 signal이 갱신되지 않거나, 특정 enum/value가 나타나야 하거나 나타나지 않아야 하는 조건을 만족하지 못하는 현상.

대표 rule:
- `ld.LD_RBD_Update`
- `ld.LD_RBD_VAL_CHECK`
- `ld.LD_RBD_IS_EXIST`

## 4. TS: Traffic Sign

Feature 의미:
- Traffic sign recognition/sign tracking output.
- 주요 값: `Tracking_ID`, `Sign_Name`, `Sup1`, `Sup2`, `Sign_Shape`, `Long_Distance`, `Lat_Distance`, `Measurement_status`, `DBG_TOP/BOTTOM` bbox.

### DEF-TS-FN: TS / FN

정의:
- 실제/reference traffic sign이 있어야 하는데 output에 없음.

대표 rule:
- `ts.TS_FN`

### DEF-TS-MISCLASS: TS / Misclassification / FN+Misclassification / Sup1

정의:
- sign은 검출되었지만 main sign 또는 supplemental sign class가 잘못된 현상.

구분:
- `Misclassification`: sign class 오류.
- `Misclassification+Sup1`: supplemental sign까지 포함한 class 오류.
- `FN+Misclassification`: 일부 frame에서는 missing, 일부 frame에서는 wrong class인 복합 증상.
- `FN+Misclassification+Sup1`: missing + main/supplemental class 오류.

대표 reference issue type:
- `Misclassification`
- `FN+Misclassification`
- `FN+Misclassification+Sup1`
- `Misclassification+Sup1`

### DEF-TS-FP: TS / FP

정의:
- 실제/reference sign이 아닌데 sign output이 생성되는 현상.

대표 rule:
- `ts.TS_FP`
- `ts.TSR_FP`

### DEF-TS-FP-DUP: TS / FP Duplicate

정의:
- 하나의 reference sign bbox 안에 두 개 이상의 valid traffic sign output이 생성되는 중복 FP 현상.

대표 rule:
- `ts.TS_DUPLICATE_IN_REF_BBOX`

### DEF-TS-ID-RANGE: TS / ID Range

정의:
- sign tracking ID가 frame range 내에서 끊기거나 새 ID로 재검출되는 현상.

대표 rule:
- `ts.TS_VALUE_JUMP` with `Tracking_ID`
- `ts.TS_ID_CONSISTENCY`

### DEF-TS-DIST-LONG: TS / Distance Long

정의:
- traffic sign longitudinal distance가 기대 range와 다르거나 같은 reference sign 그룹 내에서 차이가 과도한 현상.

대표 rule:
- `ts.TS_LONG_DIST_ERROR_RANGE`
- `ts.TS_LONG_DIST_LINEARITY`
- `ts.TS_SAME_REF_LONG_DIST_DIFF`

### DEF-TS-SHAPE: TS / Shape

정의:
- sign의 shape 분류가 기대와 다른 현상.

대표 reference issue type:
- `Shape`

### DEF-TS-MEASUREMENT: TS / Measurement_Status

정의:
- sign의 measurement status 값이 기대 상태와 다르거나 갱신되지 않는 현상.

대표 rule:
- `ts.TS_Update_Failure`
- `ts.TS_VALUE_RANGE_CHECK`

### DEF-TS-AGE-IMAGE: TS / AGE CHECK / OUT_OF_IMAGE

정의:
- sign age가 기대 범위를 벗어나거나, image 안/밖 상태가 기대와 다르게 판단되는 현상.

대표 rule:
- `ts.TS_AGE_CHECK`
- `ts.TS_OUT_OF_IMAGE_CHECK`

## 5. TL: Traffic Light

Feature 의미:
- Traffic light detection/state/spot output.
- 주요 값: `Tracking_ID`, `Long_Distance`, `Spot_Color`, `Spot_Shape`, state/sequence, debug bbox.

### DEF-TL-FN: TL / FN

정의:
- 실제/reference traffic light가 있어야 하는데 output에 없음.

대표 reference issue type:
- `FN`

### DEF-TL-FP: TL / FP

정의:
- 실제/reference traffic light가 아닌데 output이 생성되는 현상.

평가 관점:
- reference bbox와 current TL bbox 매칭.
- object rear-face 같은 virtual reference를 쓰는 경우 reference 생성 기준 확인.

### DEF-TL-DIST-LONG: TL / Distance Long

정의:
- traffic light longitudinal distance가 기대 범위와 다름.

### DEF-TL-STATE: TL / State sequence

정의:
- traffic light state 변화 순서가 기대 sequence와 다름.

### DEF-TL-SPOT: TL / Spot color/shape

정의:
- traffic light spot color 또는 shape enum이 기대값과 다름.

주요 값:
- `Spot_Color`
- `Spot_Shape`

대표 rule:
- `tl.TL_Signal_Comparison`
- `cmn.ATTRIBUTE_VALUES_MATCH`

## 6. RMD / RMD_SM / RMD_SL: Road Marking

Feature 의미:
- Road marking output.
- `RMD_SM`: symbol/marking object style.
- `RMD_SL`: stop line / line segment style.

### DEF-RMD-RANGE: RMD / RANGE_CHECK

정의:
- road marking 관련 signal이 기대 범위 밖에 있는 현상.

대표 rule:
- `rmd.RMD_RANGE_CHECK`

### DEF-RMD-UPDATE: RMD / Value_Update_Check

정의:
- road marking signal이 갱신되지 않거나 invalid 값으로 유지되는 현상.

대표 rule:
- `rmd.RMD_Value_Update_Check`

### DEF-RMD-FP: RMD_SM / FP

정의:
- 없는 road marking symbol/object가 생성되는 현상.

대표 rule:
- `rmd.RMD_FP`

### DEF-RMD-AGE-ID: RMD_SM / AGE CHECK / ID Update CHECK

정의:
- road marking age 또는 ID가 기대대로 유지/갱신되지 않는 현상.

대표 rule:
- `rmd.RMD_AGE_CHECK`
- `rmd.RMD_ID_Update_Check`

### DEF-RMD-PROB-RES: RMD_SM / Probability_jump / Resolution Range

정의:
- road marking probability가 급변하거나 resolution 관련 값이 기대 범위를 벗어나는 현상.

대표 rule:
- `rmd.RMD_Probability_jump`
- `rmd.RMD_Resolution_range`

### DEF-RMD-BBOX: RMD_SL / BBOX_Position

정의:
- road marking/stop line의 bbox 또는 position이 기대 위치와 다른 현상.

대표 rule:
- `rmd.RMD_BBOX_Position`

### DEF-RMD-DIST-JUMP: RMD_SL / Distance_jump

정의:
- stop line/road marking distance 값이 frame 간 급변하는 현상.

대표 rule:
- `rmd.RMD_Distance_jump`

## 7. FS / COMMON / OD_COMMON_HEADER

Feature 의미:
- frame-level 상태, failsafe, common header, image quality/context signal.

### DEF-FS-DATA-UPDATE: FS / Data Update Failure

정의:
- failsafe 또는 image quality signal이 기대 상태로 갱신되지 않거나 invalid 상태를 보이는 현상.

주요 signal 예:
- `Blur_Image`
- `Full_Blockag`
- `Low_Sun`
- `Out_Of_Focus`
- `Sun_Ray`
- `Partial_Blockage`
- `Fog`
- `Rain`

대표 rule:
- `cmn.VALID_RANGE_CHECK_VALUE`

### DEF-COMMON-VALUE: COMMON / Valid value, all appear, attribute match, no object

정의:
- frame-level/common output에서 특정 값이 유효 범위에 있어야 하거나, 특정 값이 나타나야/나타나지 않아야 하는 조건.

대표 rule:
- `cmn.VALID_RANGE_CHECK_VALUE`
- `cmn.VALID_VALUE_APPEARS`
- `cmn.VALID_VALUES_ALL_APPEAR`
- `cmn.ATTRIBUTE_VALUES_MATCH`
- `cmn.NO_OBJECT_DETECTED`
- `cmn.REFERENCE_VALUE_RANGE`

### DEF-OD-HEADER: OD_COMMON_HEADER / Logging or common header check

정의:
- OD common header 또는 frame-level OD metadata가 기대대로 기록/갱신되는지 확인하는 유형.

대표 rule:
- `od.OD_COMMON_HEADER_LOGGING`

## 8. CALIB: Calibration

Feature 의미:
- camera calibration state, pose, progress, reason/status signal.

### DEF-CALIB-STATE: CALIB / State

정의:
- calibration state enum이 기대 상태와 다르거나 특정 timeout/OK 상태에서 잘못 유지되는 현상.

대표 rule:
- `cal.Calib_State`
- `cal.Calib_State_During_Cal_Timeout`

### DEF-CALIB-PROGRESS: CALIB / progress / state_progress_timesync

정의:
- calibration progress 또는 time sync 관련 state progression이 기대와 다른 현상.

대표 rule:
- `cal.Calib_progress`
- `cal.Calib_state_progress_timesync`

### DEF-CALIB-POSE: CALIB / Pose

정의:
- calibration pose 값이 기대 range 밖에 있는 현상.

대표 rule:
- `cal.Calib_Pose`

### DEF-CALIB-REASON: CALIB / reason_reset / paused reason / timeout reason

정의:
- calibration reason/status field가 특정 상태 전환 후 reset되지 않거나, timeout/paused 상황에서 기대값과 다른 현상.

대표 rule:
- `cal.Error_reason_reset_at_Calib_OK`
- `cal.Calibrating_reason_reset_at_calib_OK`
- `cal.Calib_Paused_with_reason_radius`
- `cal.Calibrating_reason_at_Cal_Timeout`

## 9. CAO / CAO_HEADER: Construction Area Object

Feature 의미:
- construction area object 또는 construction area header/flag output.

### DEF-CAO-FN: CAO / FN

정의:
- construction area object/header가 있어야 하는 상황에서 output이 없음.

대표 rule:
- `cao.CAO_FN`
- `cao.CAO_Construction_Area_Flag`

### DEF-CAO-BBOX: CAO / BBOX Localization ICS

정의:
- construction area object의 image-space bbox 위치가 기대 위치와 다른 현상.

대표 rule:
- `cao.CAO_BBOX_Localization_ICS`

## 10. FSD: Freespace

Feature 의미:
- freespace segment/range/azimuth/classification output.

### DEF-FSD-RANGE: FSD / Range or freespace value check

정의:
- freespace range/azimuth/classification 값이 기대 범위 또는 기준과 다른 현상.

주요 signal:
- `FSD_Range`
- `FSD_Azimuth_Angle`
- `FSD_Class`
- `FSD_Height`

대표 rule:
- `fsd.FSD_RANGE_CHECK`

## 11. Feature 선택 가이드

```text
고객 표현 / Jira 표현                 우선 Feature
-------------------------------------------------------
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

주의:
- TSR은 workbook feature에서 보통 `TS`로 본다.
- road marking은 `RMD_SM`과 `RMD_SL`을 분리해야 한다.
- lane과 road boundary는 `LD`와 `RBD`를 분리해야 한다.
- reference JSON은 target matching을 위한 보조일 수 있고, 최종 method는 여전히 `Rule base`일 수 있다.

## 12. Rule base 해석 가이드

```text
Rule 함수 패턴                  의미
---------------------------------------------------------
*_FN                           target 누락
*_FP                           불필요 target 생성
*_RANGE / *_VALIDITY           값이 기대 range에 있는지
*_VALUE_JUMP                   frame 간 값 급변
*_Update_Failure               값 갱신 실패 / invalid 유지
*_TYPE_CLASS / Class_check     semantic class/type 오류
*_ID_*                         tracking ID 안정성 문제
*_BBOX_*                       image-space bbox 위치/중복/fit 문제
*_LOCALIZATION                 geometry/localization 문제
*_CPP                          path prediction geometry 문제
```

정성평가 시에는 rule 이름만 보고 결론 내리지 않는다.
- rule은 자동 검증의 의도를 알려준다.
- 실제 판단은 video, raw JSON, preprocessed value, reference/filter JSON, frame range, target ID/lane을 함께 읽어야 한다.
