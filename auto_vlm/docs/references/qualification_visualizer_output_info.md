# Qualification Visualizer Output Information

Purpose of this note:
- Store only the output/data-format knowledge needed to understand Qualification Visualizer outputs.
- Do not store issue definitions, pass/fail rules, or qualitative judgment logic here.
- Treat this as my local reference when later reading merged video + JSON outputs.
- Main use: when I later evaluate a case, I should understand what each JSON output value means in the scene and combine video + overlay + raw values without getting lost.

Source repo inspected:
- `C:\Users\Byeongjin Jeong\Desktop\git\Qualification_Visualizer`

Important source files:
- `run_inspector.py`
- `utils/task_manager.py`
- `utils/data_processor_fvc.py`
- `utils/data_processor_svc.py`
- `utils/data_processor_can.py`
- `utils/data_processor_lidar.py`
- `utils/aptiv/aptiv_mapping_config.py`
- `utils/sv/sv_mapping_config.py`
- `utils/aptiv/aptiv_run_visualization_fvc.py`
- `utils/aptiv/aptiv_run_visualization_svc.py`
- `utils/sv/sv_run_visualization_fvc.py`
- `config/project_modules.yaml`

## 1. Output Artifact Types

The tool combines original video frames with per-frame SW JSON output and optional CAN/Lidar data.

Generated artifacts:
- `video` mode:
  - Output file is an `.mp4`.
  - Output filename normally follows source video basename.
  - Example: source `xxx.h264` or `xxx.mp4` -> output `xxx.mp4`.
- `images` mode:
  - Output is a directory named after the source video basename.
  - Each rendered frame is saved as `00000000.jpg`, `00000001.jpg`, etc.
- Log/YAML artifacts:
  - `input_yaml.yaml`: list of log/video relative paths used for batch processing.
  - `log.txt`: processing log.

Output location:
- If `use_dynamic_video_output == True`, output directory is the parent of the log folder.
- Otherwise, output directory is `tool_output`.
- If `tool_output` is empty in CLI mode, it falls back to `<CI_output>\inspector`.

Rendering layout:
- FVC:
  - Left/main region: original camera frame with ICS overlay.
  - Right/extra region: BEV canvas appended horizontally.
- SVC:
  - Uses merge video and top-view video inputs.
  - Renders top-view/BEV style overlays depending on module settings.

## 2. Input-to-Output Processing Flow

```text
per-frame JSON files
  -> data_processor_fvc.py or data_processor_svc.py
  -> mapping config extracts raw nested JSON values
  -> processed_frame dict is created
  -> debug drawing data is merged into main objects by id/track_id
  -> draw_on_video reads matching video frame
  -> optional CAN data is added by frame index
  -> optional Lidar data is added by frame index
  -> overlay is drawn
  -> mp4 frame or jpg frame is written
```

Frame identity:
- JSON files are expected to be named like `00000000.json`.
- The numeric filename becomes the `frame` key in `processed_frame`.
- APTIV FVC has offset handling:
  - If JSON starts at `00000001.json`, `json_start_offset` may be treated as 1.
  - Render lookup uses video frame index plus offset to locate JSON frame.

FIH/SVNet multi-folder merge:
- For `path_fih`, one frame is assembled by merging JSON files with the same filename from:
  - `ADAF_json`
  - `OD_json`
  - `LD_json`
  - `FSR_json`
  - `OC_json`
  - `SC_json`
  - `FSD_bin`
- Merge is dictionary-level update before extraction.

## 3. Common Processed Frame Shape

The normalized per-frame object is conceptually:

```text
processed_frame = {
  "frame": string frame number from JSON filename,
  ... mapped scalar/list/dict keys ...
}
```

Optional runtime additions:
- `can_info`: added by GUI/data manager or drawing flow when CAN CSV exists.
- `lidar_info`: added by GUI/data manager when Lidar path exists.

Debug merge additions:
- `drawing_rect`: added to sign/light/static/construct/road-marking objects when matching debug rectangle exists.
- `drawing_points`: added to lane/road-edge/stop-line objects when matching debug points exist.

## 4. APTIV Processed Output Keys

APTIV mapping has 94 keys before post-processing.

Post-processing changes:
- `road_markings_sm` and `road_markings_sl` are removed and merged into `road_markings`.
- `dbg_*` helper lists are normally consumed and removed.
- `dbg_freespace_points` is removed.
- Main output can still contain `drawing_rect` or `drawing_points` merged from those debug lists.

### 4.1 APTIV Scalar/Dict Keys

```text
timestamp
frame_id

obj_cipv_id
obj_niv_l_id
obj_niv_r_id
obj_vd_cnt
obj_vru_cnt

traffic_signs_cnt
traffic_lights_struct_cnt

is_ca_flag
ca_obj_cnt
sod_obj_cnt
parking_space_cnt

com_sw_ver_major
com_sw_ver_minor
com_region
com_highway_flag
com_rain_intensity
com_road_type
com_vision_state

fs_blur_image
fs_frozen_windshield_lens
fs_full_blockage
fs_partial_blockage
fs_low_sun
fs_splashes
fs_sun_ray
fs_calibration_misalignment
fs_fog
fs_rain
fs_sandstorm
fs_out_of_focus
fs_out_of_calib
fs_out_of_range
fs_vision_source
fs_free_sight

fs_impacted_apa
fs_impacted_free_space
fs_impacted_heater
fs_impacted_hlb
fs_impacted_hzb
fs_impacted_hzpe
fs_impacted_isa
fs_impacted_ldw
fs_impacted_lka_lc
fs_impacted_mpa
fs_impacted_ped_aeb
fs_impacted_ped_fcw
fs_impacted_rpe
fs_impacted_tsr
fs_impacted_vbacc
fs_impacted_vd_aeb
fs_impacted_vd_fcw
fs_impacted_vpa

calb_pose_height
calb_pose_pitch_ph
calb_pose_pitch_px
calb_pose_roll
calb_pose_yaw_ph
calb_pose_yaw_px
calb_progress
calb_run_mode
calb_state
calb_status
calb_distance
calb_time
```

APTIV dict keys:

```text
cpp_lane:
  available
  confidence
  C0
  C1
  C2
  C3
  end
  start

is_highway:
  is_exit_L
  is_exit_R
  is_merge_L
  is_merge_R

intp_info:
  long_dist
  lat_dist
  type

hlb:
  hlb_brightness_score
  hlb_running_mode
  hlb_decision
  hlb_inactive_reason
  hlb_reason_approaching_junction
  hlb_reason_approaching_roundabout
  hlb_reason_bright_scene
  hlb_reason_in_blinking_trafficlight_scene
  hlb_reason_in_curve
  hlb_reason_in_roundabout
  hlb_reason_in_very_sharp_curve
  hlb_reason_lit_night
  hlb_reason_lit_night_ece
  hlb_reason_lit_night_us
  hlb_reason_low_speed
  hlb_reason_obviously_bright_scene
  hlb_reason_oncoming
  hlb_reason_oncoming_grace
  hlb_reason_sl_scene_grace
  hlb_reason_street_lights
  hlb_reason_tail_light
  hlb_reason_tail_light_grace
  hlb_reason_tunnel
```

### 4.2 APTIV List Keys and Item Fields

```text
objects[]:
  id
  class
  age
  existence_prob
  lane_assignment
  motion_status
  motion_category
  inv_ttc
  long_dist
  lat_dist
  rel_long_vel
  rel_lat_vel
  abs_long_vel
  abs_lat_vel
  width
  length
  heading
  img_coord_back_bottom_left_x
  img_coord_back_bottom_left_y
  img_coord_back_bottom_right_x
  img_coord_back_bottom_right_y
  img_coord_back_top_left_x
  img_coord_back_top_left_y
  img_coord_back_top_right_x
  img_coord_back_top_right_y
  img_coord_front_bottom_left_x
  img_coord_front_bottom_left_y
  img_coord_front_bottom_right_x
  img_coord_front_bottom_right_y
  img_coord_front_top_left_x
  img_coord_front_top_left_y
  img_coord_front_top_right_x
  img_coord_front_top_right_y
  brake_light
  left_light
  right_light

host_lanes[]:
  track_id
  role
  type
  existence_prob
  color
  C0
  C1
  C2
  C3
  start
  end
  drawing_points  # added by debug merge if available

adjacent_lanes[]:
  track_id
  role
  type
  existence_prob
  color
  C0
  C1
  C2
  C3
  start
  end
  drawing_points  # added by debug merge if available

road_edges[]:
  track_id
  role
  type
  existence_prob
  C0
  C1
  C2
  C3
  start
  end
  drawing_points  # added by debug merge if available

traffic_signs[]:
  id
  sign_name
  confidence
  long_dist
  lat_dist
  sup1_sign_name
  sup2_sign_name
  relevancy
  drawing_rect  # added by debug merge if available

traffic_lights[]:
  id
  struct_state
  type_confidence
  long_dist
  lat_dist
  drawing_rect  # added by debug merge if available

road_markings[]:
  For SM items:
    kind
    id
    age
    type
    lat_dist
    long_dist
    orientation
    width
    depth
    drawing_rect  # added by debug merge if available
  For SL items:
    kind
    id
    age
    type
    lat_dist_L
    lat_dist_R
    long_dist_L
    long_dist_R
    drawing_points  # added by debug merge if available

construct_object[]:
  id
  age
  type
  lat_dist
  long_dist
  width
  height
  drawing_rect  # added by debug merge if available

static_object[]:
  id
  age
  type
  lat_dist
  long_dist
  width
  height
  orientation
  drawing_rect  # added by debug merge if available

parking_space[]:
  id
  class
  type
  status
  existence_prob
  width
  depth
  P0
  P1
  P2
  P3
  validity
  condition

fsd_element[]:
  range
  azimuth
  classification_type

lsv[]:
  type
  id
  vd_id
  drawing_rect  # added by debug merge if available
```

### 4.3 APTIV Debug Helper Lists

These are extracted from raw JSON, then usually consumed into main objects and removed.

```text
dbg_host_lanes_points[]:
  id
  points

dbg_adjacent_lanes_points[]:
  id
  points

dbg_road_edges_points[]:
  id
  points

dbg_freespace_points[]:
  x
  y

dbg_traffic_signs_rects[]:
  id
  bottom_x
  bottom_y
  top_x
  top_y

dbg_traffic_lights_rects[]:
  id
  bottom_x
  bottom_y
  top_x
  top_y

dbg_road_markings_sm_rects[]:
  kind
  id
  type
  bottom_x
  bottom_y
  top_x
  top_y

dbg_road_markings_sl_points[]:
  kind
  id
  type
  x
  y

dbg_construct_object_rects[]:
  id
  bottom_x
  bottom_y
  top_x
  top_y

dbg_static_object_rects[]:
  id
  bottom_x
  bottom_y
  top_x
  top_y

dbg_lsv_object_rects[]:
  id
  bottom_x
  bottom_y
  top_x
  top_y
```

Lane/edge debug `points` are converted to:

```text
drawing_points[]:
  width = DBG_Line_Width
  x     = DBG_Point.DBG_Point_X
  y     = DBG_Point.DBG_Point_Y
```

## 5. FIH/SVNet Processed Output Keys

SV/FIH mapping has 51 keys before post-processing.

FIH/SVNet module folders:

```text
CMN_LOG_TYPES = [
  ADAF,
  OD,
  LD,
  FSR,
  OC,
  SC,
  FSD
]
```

### 5.1 SV/FIH Scalar/Dict Keys

```text
frame_id

obj_cipv_id
obj_niv_l_id
obj_niv_r_id

sc_construction_area1
sc_construction_area2
sc_highway
sc_road_type
sc_time
sc_tollgate
sc_tunnel
sc_weather

fs_impacted_free_space
fs_impacted_heater
fs_impacted_hlb
fs_impacted_hzb
fs_impacted_hzpe
fs_impacted_ld_lc
fs_impacted_ped_aeb
fs_impacted_ped_fcw
fs_impacted_rpe
fs_impacted_tsr
fs_impacted_vbacc
fs_impacted_vd_aeb
fs_impacted_vd_fcw

calb_pose_height
calb_pose_pitch_ph
calb_pose_pitch_px
calb_pose_roll
calb_pose_yaw_ph
calb_pose_yaw_px
calb_progress
calb_run_mode
calb_state
calb_status
calb_distance
calb_time
```

SV/FIH dict keys:

```text
cpp_lane:
  available
  confidence
  C0
  C1
  C2
  C3
  end
  start

fs_blur_image:
  state
  severity_level

fs_fog:
  state
  severity_level

fs_full_blockage:
  state
  severity_level

fs_partial_blockage:
  state
  severity_level

fs_sun_ray:
  state
  severity_level

fs_low_sun:
  state
  severity_level

fs_out_of_focus:
  state
  severity_level
```

### 5.2 SV/FIH List Keys and Item Fields

```text
adaf_objects[]:
  id
  lane_id
  motion_category
  motion_orientation
  motion_status

objects[]:
  id
  class
  age
  existence_prob
  lane_assignment
  ttc
  long_dist
  lat_dist
  rel_long_vel
  rel_lat_vel
  abs_long_vel
  abs_lat_vel
  width
  length
  heading
  box_2d
  box_3d_faces
  sign_key
  sign_key_sup1
  sign_key_sup2

host_lanes[]:
  drawing_points
  track_id
  confidence
  role
  type
  color
  C0
  C1
  C2
  C3
  start
  end

road_edges[]:
  drawing_points
  track_id
  confidence
  role
  type
  color
  C0
  C1
  C2
  C3
  start
  end

fsd_element[]:
  range
  azimuth
  classification_type
  long_dist
  lat_dist

fsd_ics_point[]:
  x
  y
```

SV/FIH object note:
- `objects[]` may include regular objects plus traffic/static categories depending on class/sign keys.
- The SV visualizer separates objects into vehicle/pedestrian, traffic signs, traffic lights, and static objects during drawing by class/category logic.

## 6. CAN Output Added at Runtime

CAN source:
- CSV file.
- Header row is detected by first column containing `Time` or `Timestamp`.
- Frame column is `CAM_<can_num>`.
- Missing exact frame uses previous available frame value.

Canonical CAN keys:

```text
can_info:
  CAM
  YawRate
  SteeringAngle
  LongAccel
  LatAccel
  Gear
  VehicleSpeed
  WheelSpeed FL
  WheelSpeed FR
  WheelSpeed RL
  WheelSpeed RR
```

Raw CSV possible column names:

```text
CAM:
  CAM_<can_num>

YawRate:
  Yaw_Rate
  YAW_RATE

SteeringAngle:
  Steering_Angle
  SAS_ANGLE
  SAS_Angle

LongAccel:
  Longitudinal_Acceleration
  LONG_ACCEL

LatAccel:
  Lateral_Acceleration
  LAT_ACCEL

Gear:
  Gear_Position
  G_SEL_DISP

VehicleSpeed:
  Cluster_Display_Speed
  CF_Clu_Vanz

WheelSpeed FL:
  Wheel_Speed_FL
  WHL_SPD_FL

WheelSpeed FR:
  Wheel_Speed_FR
  WHL_SPD_FR

WheelSpeed RL:
  Wheel_Speed_RL
  WHL_SPD_RL

WheelSpeed RR:
  Wheel_Speed_RR
  WHL_SPD_RR
```

## 7. Lidar Output Added at Runtime

Lidar source:
- Per-frame JSON files named by frame number.
- JSON root key expected: `object`.

Runtime output:

```text
lidar_info[]:
  name
  id
  long_dist
  lat_dist
  width
  length
  yaw
  bbox2d
  velocity
```

Field mapping:

```text
name      <- object.name
id        <- object.tracking_id
long_dist <- object.bbox3d.x
lat_dist  <- object.bbox3d.y
width     <- object.bbox3d.w
length    <- object.bbox3d.l
yaw       <- object.bbox3d.yaw

bbox2d:
  x1 <- object.bbox2d.x1
  y1 <- object.bbox2d.y1
  x2 <- object.bbox2d.x2
  y2 <- object.bbox2d.y2

velocity:
  x <- object.velocity.x
  y <- object.velocity.y
```

## 8. Module Visibility Config

Module visibility is loaded from:
- `config/project_modules.yaml`

Projects currently defined:
- `fvc_aptiv_ceer`
- `fvc_aptiv_china`
- `fvc_aptiv_field`
- `svc_aptiv_ceer`
- `fvc_FIH`

Main view sections:
- `ICS`: image/camera-space overlay and text overlays.
- `BEV`: bird's-eye-view canvas overlay.
- `TOP`: SVC top-view overlay.

Common module toggles:

```text
CAN
COM
SC
OD
LD
RE
TS
TL
RM
SOD
CA
FS
Calib
HLB
LSD
CPP
FSD
INTP
LIDAR
PSD
```

Important detail:
- A key can exist in `processed_frame` but not be visible if the module is disabled in project config.
- Some module settings are booleans; some are dictionaries with `enabled` and `details`.

## 9. What the Visual Output Actually Draws

FVC APTIV/SV common drawing categories:

```text
Base:
  original camera frame
  BEV background grid
  test case name
  frame number

CAN:
  can_info text block

Common / SC:
  SW version / region / vision state / road type / rain / highway / scene classification fields

OD:
  objects on ICS
  objects on BEV
  CIPV/NIV labels from obj_cipv_id, obj_niv_l_id, obj_niv_r_id

LD:
  host_lanes
  adjacent_lanes if present

RE:
  road_edges

CPP:
  cpp_lane path prediction

INTP:
  intp_info

TS:
  traffic_signs or sign-like SV objects

TL:
  traffic_lights or light-like SV objects

RM:
  road_markings

SOD/CA/LSV:
  static_object
  construct_object
  lsv

FSD:
  fsd_element
  fsd_ics_point for SV/FIH

FS:
  failsafe text/status values

Calib:
  calibration current pose/status/progress fields

LIDAR:
  lidar_info on BEV
  lidar_info bbox2d on ICS if available
```

SVC APTIV drawing categories:

```text
Base:
  merge video
  top-view video
  BEV background grid

OD:
  objects on top-view
  objects on BEV

LD/RE:
  polynomial lanes and road edges on top-view and BEV

PSD:
  parking_space on top-view and BEV

SOD:
  static_object on top-view and BEV

FSD:
  fsd_element / freespace visualization

RM:
  road_markings

CAN/COM/FS:
  text blocks if enabled
```

## 10. Coordinate/Field Meaning Used by Drawing

Distance fields:

```text
long_dist:
  longitudinal distance in vehicle coordinates.

lat_dist:
  lateral distance in vehicle coordinates.

width / length:
  physical object size for BEV/top-view boxes.

heading / yaw:
  orientation used to rotate BEV/top-view boxes.
```

Image-space fields:

```text
drawing_rect:
  bottom_x
  bottom_y
  top_x
  top_y
  Used as 2D rectangle on original image.

drawing_points:
  x
  y
  width
  Used as polyline or point sequence on original image.

APTIV object 3D image corner fields:
  img_coord_back_bottom_left_x/y
  img_coord_back_bottom_right_x/y
  img_coord_back_top_left_x/y
  img_coord_back_top_right_x/y
  img_coord_front_bottom_left_x/y
  img_coord_front_bottom_right_x/y
  img_coord_front_top_left_x/y
  img_coord_front_top_right_x/y

SV object image fields:
  box_2d
  box_3d_faces
```

Line model fields:

```text
C0, C1, C2, C3:
  polynomial coefficients for lane/edge/path drawing.

start, end:
  longitudinal range for drawing polynomial line.

role / type / color / confidence / existence_prob:
  displayed text and/or line style/color selection.
```

## 11. YAML Input Format Used to Produce Outputs

Batch YAML entries look like:

```yaml
- log_rel_path: A0_sample/20240603_145000/SV_INSPECTOR_json
  mp4_rel_path: A0_sample_Korea/20240603_145000/KOR_TM5887_M_20240603_145000_cam.h264
```

SVC entries may carry paired video info internally as merge/top video paths.

Task tuple shape used by `process_video_task`:

```text
(log_path, video_info, can_path, can_num, lidar_path)

FVC:
  video_info = full_video_path string

SVC:
  video_info = (full_merge_path, full_top_path)
```

## 12. Output Information Summary for Auto VLM Use

When I later receive a rendered output video/image from this tool, the visible overlay should be interpreted as:

```text
Original pixels:
  Raw video frame.

Overlay geometry:
  Directly derived from processed_frame keys and optional debug fields.

Text blocks:
  Directly derived from common, CAN, failsafe, calibration, count, or object fields.

BEV/Top geometry:
  Derived from long_dist, lat_dist, width, length, heading/yaw, lane coefficients, and freespace fields.

Visibility:
  Controlled by project_modules.yaml, so absence on screen does not always mean absence in JSON.
```

This document intentionally contains only output structure and visualization mapping information.

## 13. Semantic Meaning of Important JSON Values

This section is not an issue checklist. It is the meaning of values so I can interpret output consistently.

### 13.1 Frame and Time Values

```text
frame:
  Frame number derived from JSON filename.
  This is the primary index used to match one JSON output to one video frame.

frame_id:
  Algorithm frame id from SW output.
  This may be different from filename frame depending on pipeline/export behavior.

timestamp:
  SW output timestamp in milliseconds for APTIV common output.
  Useful for understanding temporal ordering, but visualizer mainly uses frame index.
```

How to read:
- `frame` tells which visual frame the JSON belongs to in this tool.
- `frame_id` tells which internal algorithm frame the SW says it processed.
- If video, filename frame, and `frame_id` do not intuitively line up, the values still represent different clocks/indexes rather than the same field.

### 13.2 Object Identity and Role Values

```text
objects[].id:
  Tracking id for a detected object.
  Same id over adjacent frames means the SW thinks it is the same physical target.

obj_cipv_id:
  ID of the object selected as CIPV.
  CIPV means closest/in-path primary vehicle target used by ADAS logic.

obj_niv_l_id:
  ID of the selected neighboring in-path/near target on the left side.

obj_niv_r_id:
  ID of the selected neighboring in-path/near target on the right side.

lane_assignment:
  Lane relationship assigned to the object.
  Used by drawing and target-role context.

age:
  Lifetime or persistence counter of the detection/track.
  Higher age usually means the target has persisted longer.

existence_prob / confidence:
  Probability/confidence that the output item exists or is reliable.
```

How to read:
- Object role values are linked through IDs.
- If `obj_cipv_id = 12`, then the object in `objects[]` with `id = 12` is the CIPV target.
- Text labels in the rendered output usually come from these ID relationships.

### 13.3 Object Class and Motion Values

```text
objects[].class:
  Category/type of detected object.
  Drawing config maps numeric class to names/colors.

motion_status:
  Current motion state of object, such as moving/stationary style states depending on project enum.

motion_category:
  Higher-level motion category.

heading:
  Object orientation angle used for BEV box rotation.

rel_long_vel:
  Relative longitudinal velocity versus ego vehicle.

rel_lat_vel:
  Relative lateral velocity versus ego vehicle.

abs_long_vel:
  Absolute longitudinal velocity.

abs_lat_vel:
  Absolute lateral velocity.

inv_ttc / ttc:
  Time-to-collision related value.
  APTIV uses inverse TTC field; SV/FIH uses TTC field.
```

How to read:
- `class` says what kind of target the SW thinks it is.
- `long_dist`, `lat_dist`, `width`, `length`, and `heading` define where/how the object appears in BEV.
- Image-space corners/boxes define where it is drawn on the camera image.
- Velocity and TTC-related fields describe dynamic behavior, not only visual position.

### 13.4 Object Position and Size Values

```text
long_dist:
  Object longitudinal position in ego/vehicle coordinates.
  Positive values generally mean in front of ego.

lat_dist:
  Object lateral position in ego/vehicle coordinates.
  Sign convention depends on project coordinate system, but it is used as left/right BEV offset.

width:
  Object physical width.

length:
  Object physical length/depth.

heading / yaw:
  Object orientation angle for rotated BEV/top-view drawing.
```

How to read:
- BEV object drawing mostly comes from these fields.
- Camera image box and BEV location are two different projections of the same detection output.
- When understanding a target, combine:
  - object ID
  - class
  - long/lat distance
  - size
  - heading/yaw
  - image box/corners
  - role ID such as CIPV/NIV

### 13.5 Image-Space Object Values

APTIV object 3D corner fields:

```text
img_coord_back_bottom_left_x/y
img_coord_back_bottom_right_x/y
img_coord_back_top_left_x/y
img_coord_back_top_right_x/y
img_coord_front_bottom_left_x/y
img_coord_front_bottom_right_x/y
img_coord_front_top_left_x/y
img_coord_front_top_right_x/y
```

SV/FIH image-space fields:

```text
box_2d:
  2D image box.

box_3d_faces:
  3D box face coordinates projected into image.
```

Debug rectangle fields:

```text
drawing_rect:
  top_x
  top_y
  bottom_x
  bottom_y
```

How to read:
- Image-space values are pixel/projection values used to draw on the original video.
- BEV values are metric vehicle-coordinate values.
- They are complementary; one explains where it appears in the image, the other explains where the SW places it around ego.

### 13.6 Lane and Road Edge Values

```text
host_lanes[]:
  Lane boundaries belonging to or directly related to ego lane.

adjacent_lanes[]:
  Lane boundaries for neighboring lanes.

road_edges[]:
  Road boundary or drivable-road edge features.

track_id:
  Tracking id of lane/edge feature.

role:
  Functional role of the line, such as left/right/host/adjacent depending on enum mapping.

type:
  Line type/category, such as solid/dashed/edge-like depending on enum mapping.

color:
  Lane color/category when available.

C0, C1, C2, C3:
  Polynomial coefficients describing line geometry.

start, end:
  Longitudinal range where the line is valid/drawn.

drawing_points:
  Pixel-space debug points for drawing the line on the image.
```

How to read:
- Polynomial fields describe the lane/edge in vehicle coordinates.
- `drawing_points` are image-space debug points used for overlay.
- `track_id` links the logical lane/edge result to its debug drawing points.
- For visual understanding, line meaning comes from both its role/type and its geometry.

### 13.7 CPP and INTP Values

```text
cpp_lane:
  Center/path prediction output.
  It has available/confidence plus polynomial C0-C3 and start/end range.

intp_info:
  Interpolation/path-related point or type information.
  Contains long_dist, lat_dist, and type.

is_highway:
  Lane application/context flags such as exit/merge left/right.
```

How to read:
- `cpp_lane` is not a detected lane marking; it is a predicted path-like output.
- `host_lanes`/`road_edges` describe perceived road geometry.
- `cpp_lane` describes the path prediction derived or selected by application logic.

### 13.8 Traffic Sign Values

```text
traffic_signs[].id:
  Tracking/id for sign output.

sign_name:
  Main sign class.

sup1_sign_name / sup2_sign_name:
  Supplemental sign classes attached to the main sign.

confidence:
  Confidence of sign classification/existence.

long_dist / lat_dist:
  Sign position in vehicle coordinates.

relevancy:
  Whether/how the sign is relevant to ego/context, based on SW output enum.

drawing_rect:
  Pixel-space debug rectangle used to draw the sign on image.

traffic_signs_cnt:
  Header-level sign count.
```

How to read:
- `sign_name` is what the sign is.
- `relevancy` is whether the SW treats it as applicable to ego/context.
- `long_dist`/`lat_dist` say where the sign is placed in scene coordinates.
- `drawing_rect` says where the visualizer draws it on the image.

### 13.9 Traffic Light Values

```text
traffic_lights[].id:
  Tracking/id for traffic light structure.

struct_state:
  Traffic light state/class enum.

type_confidence:
  Confidence of the traffic light type/state output.

long_dist / lat_dist:
  Traffic light structure position in vehicle coordinates.

drawing_rect:
  Pixel-space debug rectangle.

traffic_lights_struct_cnt:
  Header-level traffic light structure count.
```

How to read:
- `struct_state` is the important semantic state.
- Position is metric via long/lat, and image location is via `drawing_rect`.

### 13.10 Road Marking Values

Road markings are merged into one `road_markings[]` list.

```text
kind:
  Marking source/type marker.
  Common values in processing are sm_mark and sl_mark.

SM-style fields:
  id
  age
  type
  lat_dist
  long_dist
  orientation
  width
  depth
  drawing_rect

SL-style fields:
  id
  age
  type
  lat_dist_L
  lat_dist_R
  long_dist_L
  long_dist_R
  drawing_points
```

How to read:
- SM-style entries behave like rectangular road markings.
- SL-style entries behave like stop-line/line markings with endpoints or points.
- The `kind` field is needed before interpreting which field set is meaningful.

### 13.11 Static Object, Construction, LSV, and Parking Values

```text
construct_object[]:
  Construction-area related objects.
  Fields: id, age, type, lat_dist, long_dist, width, height, drawing_rect.

static_object[]:
  Static obstacle/object outputs.
  Fields: id, age, type, lat_dist, long_dist, width, height, orientation, drawing_rect.

lsv[]:
  Light scene vehicle related output.
  Fields: type, id, vd_id, optional drawing_rect.

parking_space[]:
  Parking-slot output for SVC.
  Fields include id, class, type, status, existence_prob, width, depth, P0-P3, validity, condition.
```

How to read:
- `construct_object` and `static_object` are scene-object outputs separate from regular dynamic `objects[]`.
- `parking_space` uses corner points `P0` to `P3` and status/validity fields rather than normal object long/lat box only.

### 13.12 Freespace Values

```text
fsd_element[]:
  Freespace output elements.
  APTIV fields: range, azimuth, classification_type.
  SV/FIH fields: range, azimuth, classification_type, long_dist, lat_dist.

fsd_ics_point[]:
  SV/FIH image-space freespace contour points.
  Fields: x, y.

dbg_freespace_points[]:
  APTIV debug freespace points extracted but normally removed after processing.
```

How to read:
- Freespace is not an object list; it represents available/blocked contour or segment-style space.
- APTIV BEV drawing converts range/azimuth-type information.
- SV/FIH may include direct long/lat and ICS image contour points.

### 13.13 Common / Scene / Failsafe Values

APTIV common:

```text
com_sw_ver_major / com_sw_ver_minor:
  SW version fields.

com_region:
  Region code.

com_highway_flag:
  High-speed/highway road flag.

com_rain_intensity:
  Rain intensity output.

com_road_type:
  Road type enum.

com_vision_state:
  Vision system state enum.
```

SV/FIH scene classification:

```text
sc_construction_area1 / sc_construction_area2:
  Construction area scene classification outputs.

sc_highway:
  Highway entrance/context output.

sc_road_type:
  Road type classification.

sc_time:
  Time-of-day classification.

sc_tollgate:
  Tollgate entrance/context output.

sc_tunnel:
  Tunnel entrance/context output.

sc_weather:
  Weather classification.
```

Failsafe:

```text
fs_blur_image
fs_frozen_windshield_lens
fs_full_blockage
fs_partial_blockage
fs_low_sun
fs_splashes
fs_sun_ray
fs_calibration_misalignment
fs_fog
fs_rain
fs_sandstorm
fs_out_of_focus
fs_out_of_calib
fs_out_of_range
fs_vision_source
fs_free_sight
```

Impacted technology fields:

```text
fs_impacted_*
```

How to read:
- Common and scene values describe global frame context.
- Failsafe values describe perception degradation or impacted downstream function state.
- These fields explain status text overlays; they are not object geometry.

### 13.14 Calibration Values

```text
calb_pose_height:
  Current camera/vehicle calibration height value.

calb_pose_pitch_ph / calb_pose_pitch_px:
  Current pitch value in different units/representations.

calb_pose_roll:
  Current roll value.

calb_pose_yaw_ph / calb_pose_yaw_px:
  Current yaw value in different units/representations.

calb_progress:
  Calibration progress.

calb_run_mode:
  Calibration running mode.

calb_state:
  Calibration state.

calb_status:
  Calibration status.

calb_distance:
  Distance accumulated/used for calibration.

calb_time:
  Time accumulated/used for calibration.
```

How to read:
- Calibration values are frame-level state values.
- They are used for status/pose overlays, not object/lane drawing directly in this output note.

### 13.15 CAN Values

```text
VehicleSpeed:
  Ego vehicle speed.

YawRate:
  Ego yaw rate.

SteeringAngle:
  Steering wheel/steering angle signal.

LongAccel:
  Ego longitudinal acceleration.

LatAccel:
  Ego lateral acceleration.

Gear:
  Gear position.

WheelSpeed FL/FR/RL/RR:
  Individual wheel speed signals.

CAM:
  Camera frame column used to align CAN row to video frame.
```

How to read:
- CAN values are ego-vehicle state, not perception outputs.
- They are aligned by frame index using `CAM_<can_num>`.
- If exact frame data is missing, the previous available CAN row is used.

### 13.16 Lidar Values

```text
lidar_info[].id:
  Lidar tracking id.

name:
  Lidar object label/name.

long_dist / lat_dist:
  Lidar object position from bbox3d x/y.

width / length:
  Lidar bbox3d size.

yaw:
  Lidar bbox3d orientation.

bbox2d:
  Lidar image-space rectangle if present.

velocity.x / velocity.y:
  Lidar object velocity components.
```

How to read:
- Lidar values are separate sensor/reference output loaded from Lidar JSON.
- They can appear in BEV and optionally image overlay if `bbox2d` is present.
- Lidar IDs are not the same namespace as camera object IDs unless explicitly matched by later logic.

## 14. How to Combine Values Without Issue Assumptions

When later reading a frame, the output values should be grouped like this:

```text
Scene/frame context:
  frame, frame_id, timestamp
  common / scene classification
  failsafe
  calibration
  CAN ego state

Dynamic targets:
  objects[]
  obj_cipv_id / obj_niv_l_id / obj_niv_r_id
  object class, motion, distance, velocity, image projection

Road model:
  host_lanes[]
  adjacent_lanes[]
  road_edges[]
  cpp_lane
  intp_info

Landmarks and signals:
  traffic_signs[]
  traffic_lights[]
  road_markings[]

Static/drivable-space outputs:
  static_object[]
  construct_object[]
  parking_space[]
  fsd_element[]
  fsd_ics_point[]

External/reference runtime data:
  can_info
  lidar_info
```

Meaning combination rule:
- A visual overlay element is usually not a standalone fact. It is a rendered form of several JSON values.
- For an object, read ID + class + role + position + motion + image projection together.
- For a lane/edge, read role/type + polynomial/range + drawing_points together.
- For a sign/light, read class/state + relevancy/confidence + position + drawing_rect together.
- For scene state, read common/SC/failsafe/calibration/CAN as frame context around the perception outputs.

This still does not define whether anything is an issue. It only defines how to understand what the output is saying.
