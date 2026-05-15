# QV FVC Image Legend

This reference summarizes how Qualification Visualizer FVC screenshots are drawn. Use it to interpret issue capture images together with the parsed JSON context.

## Capture Layout
- Left side: original camera / ICS view with JSON perception drawings and optional LiDAR drawings.
- Right side: BEV (bird's-eye view) generated from the same log data.
- Issue target highlight: yellow rectangle in the camera/ICS view and yellow circle in BEV when the capture script can identify the target.
- Use the camera/ICS view for visibility, occlusion, object box quality, edge-of-FOV, and road-scene context.
- Use BEV for longitudinal/lateral position, ego-path relevance, green Road Edge line or median separation, adjacent-lane relevance, and non-drivable-area judgment.
- Do not judge by color alone. Prefer target ID, class/label text, parsed JSON values, and the yellow issue highlight.

## Drawing Order
QV draws layers roughly in this order:
- CAN/common information and optional LiDAR overlays
- FSD/free-space in BEV
- road markings, host lanes, adjacent lanes, road edges
- OD objects
- TS/TL landmarks
- construction/SOD/static objects
- object counts and auxiliary BEV labels

Later layers may visually cover earlier layers, so an object can be partially hidden by another overlay.

## OD Object Drawing
- OD objects come from `avi_objects/VIS_OBJ_Element` in the JSON mapping.
- Important mapped signals include object id, class, age, existence probability, lane assignment, motion status/category, inverse TTC, longitudinal/lateral distance, relative and absolute velocities, width, length, heading, and image coordinates.
- ICS label format is usually `[id] CLASS_ABBR`, for example `CAR`, `TRK`, `MBK`, `BCY`, `PED`, `2WH`.
- OD distance text can show `long_dist, lat_dist` near the box.
- OD velocity text can show absolute velocity in kph.
- CIPV/NIV and TTC text can be drawn near the center; CIPV is safety-critical if it is in the ego path.
- BEV draws vehicles/trucks as rotated polygons and pedestrians as circles. BEV text can include id and lane assignment.
- OD BEV position is based on rear-center long/lat converted to geometric center using heading and length.
- Heading arrows may be drawn on the ICS box.

Common visual colors, from OpenCV BGR constants:
- CAR: red
- TRUCK: blue
- PEDESTRIAN: green
- MOTORBIKE/BICYCLE/2-WHEELER: yellow
- ANIMAL: magenta
- CIPV emphasis: red fill/text in BEV or text area
- NIV emphasis: green fill/text in BEV or text area

## LiDAR Drawing
- LiDAR objects are optional and are drawn when LiDAR data exists.
- ICS uses the LiDAR 2D bbox.
- BEV uses a rotated box if dimensions and heading are available; otherwise it may use a circle.
- LiDAR labels include LiDAR id/name when available.
- LiDAR drawing color is cyan/yellow-ish in the code's BGR tuple, with white BEV text.
- For LiDAR FN, the target is a LiDAR object that may not have a valid matched camera perception object.
- For LiDAR FP, a stable/high-confidence camera object can indicate that the camera object is probably valid rather than a true FP.

## Lane, Road Edge, And Road Marking Drawing
- Host and adjacent lanes come from `avi_lanes_host/VIS_LH_Element` and `avi_lanes_adjacent/VIS_LA_Element`.
- Road edges come from `avi_lanes_road_edge/VIS_LRE_Element`.
- Road Edge is drawn as a green line in both ICS and BEV; text can show track id and road-edge type.
- Road-edge types include flat, elevated structure, curb, cones/poles, and parking cars.
- Lane colors are based on the JSON lane color enum. Lane text can show track id, lane type, role, and color.
- Road markings are drawn in gray.
- If a green Road Edge line is clearly between the host vehicle and target object, or the target is separated by a median/non-drivable region, lower the ADAS/AD safety relevance unless the object can still affect the ego path.

## FSD / Free-Space Drawing
- FSD is drawn in BEV from `avi_freespace/VIS_FSD_SegmentElement`.
- The FSD polygon is semi-transparent green.
- FSD points can be colored by classification such as guardrail, curb, road edge, visibility limit, unknown, object, or wall.
- FSD is the drivable/free-space estimate, but it can naturally terminate at vehicles, pedestrians, or obstacles. Use it only as supporting context, not as a standalone reason to dismiss an issue.
- For VRU cases, remember that a pedestrian on the drivable path may naturally terminate FSD in front of the pedestrian. Do not exclude such a VRU only because FSD ends at the object.

## TS, TL, SOD, And Construction Drawing
- Traffic signs come from `avi_traffic_signs/VIS_TSR_Element`.
- Traffic lights come from `avi_traffic_lights/VIS_TFL_StructElement`.
- SOD/static objects come from `avi_staticobjects/VIS_SOD_Element`.
- TS/TL/CA landmarks are rectangles in ICS and circles in BEV.
- TS text usually includes `[id] sign_name`; supplemental signs may also appear.
- TL text usually includes `[id] traffic light state`.
- SOD/construction/static objects use their own drawing color and labels.

## QA Interpretation Rules
- First identify the highlighted target in both views. If the yellow highlight points to the wrong object, mention possible capture/target-sync risk and rely more on row data and parsed JSON.
- For distance or velocity mismatch, compare the issue signal value, LiDAR/reference value, and delta. Use BEV to decide whether the mismatch matters for ego control.
- For TTC risk, judge TTC together with lateral offset, object role (CIPV/NIV/adjacent), road edge/median separation, and near-field safety impact.
- For heading change, judge whether the object is in the relevant ROI and whether the jump would affect tracking continuity or control logic.
- For LiDAR FN, consider whether the LiDAR object is occluded by a nearer LiDAR object. A far object behind a nearer occluding object can be lower priority or non-issue.
- For LiDAR FP, consider whether a stable, high-confidence camera object is actually valid even if LiDAR matching failed.
