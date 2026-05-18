# QV FVC Image Legend

Use this reference to interpret Qualification Visualizer FVC issue screenshots together with the parsed JSON context. The screenshot provides visual relevance; the JSON context provides exact values.

## 1. Screenshot Layout
- Left side: original camera / ICS view with JSON perception drawings and optional LiDAR drawings.
- Right side: BEV (bird's-eye view) generated from the same log data.
- Issue target highlight:
  - ICS: yellow rectangle around the target object when available.
  - BEV: yellow circle on or near the target object's rear-center reference point when available.
- First identify the same target in both views by row label, object id, class text, and the yellow highlight. If the highlight appears wrong, report possible capture/target-sync risk and rely more on parsed JSON.

## 2. BEV Coordinate And Scale
- The blue rectangle near the bottom center of BEV is the host/ego vehicle.
- Use the blue ego box as the reference for ego path, longitudinal distance, lateral offset, and control relevance.
- The BEV grid spacing is 5 meters per cell.
- Use the grid only for approximate visual scale. Use parsed JSON for exact distances, speeds, TTC, and deltas.

## 3. OD Object Position And Kinematics
- OD objects come from `avi_objects/VIS_OBJ_Element`.
- Important JSON fields include object id, class, age, existence probability, lane assignment, motion status/category, inverse TTC, `long_dist`, `lat_dist`, relative/absolute velocities, width, length, heading, and image coordinates.
- JSON `long_dist` and `lat_dist` correspond to the object's rear-center reference point.
- In BEV, the small white point on an OD box marks this rear-center long/lat reference. Judge distance from ego to this point, not from ego to the visual center of the rotated box.
- The BEV OD box may be drawn as a rotated polygon using heading and length. Use the rotated box orientation together with JSON `heading` to judge whether the object is aligned with traffic, crossing, oncoming, or moving toward the host lane.
- ICS label format is usually `[id] CLASS_ABBR`, such as `CAR`, `TRK`, `MBK`, `BCY`, `PED`, or `2WH`.
- OD distance text may show `long_dist, lat_dist` near the box.
- OD velocity text may show absolute velocity in kph, but JSON velocity values are the primary source.
- Heading arrows may be drawn on the ICS box.

Common OD colors:
- CAR: red
- TRUCK: blue
- PEDESTRIAN: green
- MOTORBIKE/BICYCLE/2-WHEELER: yellow
- ANIMAL: magenta
- CIPV emphasis: red fill/text in BEV or text area
- NIV emphasis: green fill/text in BEV or text area

## 4. Lane, Road Edge, Road Marking, And FSD
- Lane and Road Edge detections are drawn in both ICS and BEV.
- Road Edge is always a green line. Treat a clear green Road Edge line as a strong boundary/separation cue.
- Normal lanes use the detected lane color. For example, a detected white lane marking is drawn as a white line.
- Do not confuse ordinary lane markings with Road Edge. A normal lane line is weaker separation evidence than a Road Edge, median, barrier, curb, or non-crossable obstacle.
- Road edges come from `avi_lanes_road_edge/VIS_LRE_Element`; road-edge types can include flat, elevated structure, curb, cones/poles, or parking cars.
- Host and adjacent lanes come from `avi_lanes_host/VIS_LH_Element` and `avi_lanes_adjacent/VIS_LA_Element`.
- Road markings are drawn in gray.
- FSD/free-space is drawn in BEV as a semi-transparent green area/polygon.
- Distinguish green Road Edge lines from the semi-transparent green FSD/free-space area. Road Edge is a boundary cue; FSD is only supporting context.
- FSD can naturally stop at vehicles, pedestrians, walls, curbs, or obstacles. Do not use FSD termination alone to dismiss an issue.

## 5. Road Scene And Driving Context
- Use ICS/BEV to classify the road-scene context when it is visually clear: highway/high-speed road, arterial/city road, intersection, underpass/bridge shadow, parking lot, stopped traffic, congestion, or low-speed maneuvering.
- Use parsed JSON road context when available, such as `com_highway_flag`, `com_road_type`, `com_region`, and `is_highway`.
- Use CAN/JSON vehicle speed if available. Do not infer exact host speed from the image alone.
- For the same close-object instability, raise priority in highway/high-speed-road or visually high-speed contexts because reaction time and control risk are higher.
- Lower priority in parking lots, traffic jams, stopped traffic, or clearly low-speed maneuvering when the object is not in the ego path and control impact is limited.
- If road type or speed is uncertain, say it is uncertain and avoid over-weighting the scene context.

## 6. LiDAR Drawing
- LiDAR objects are optional and are drawn only when LiDAR data exists.
- ICS uses the LiDAR 2D bbox.
- BEV uses a rotated box if dimensions and heading are available; otherwise it may use a circle.
- LiDAR labels include LiDAR id/name when available.
- For LiDAR FN, the target is a LiDAR object that may not have a valid matched camera perception object.
- For LiDAR FP, a stable/high-confidence camera object can indicate that the camera object is probably valid even if LiDAR matching failed.

## 7. TS, TL, SOD, And Construction Drawing
- Traffic signs come from `avi_traffic_signs/VIS_TSR_Element`.
- Traffic lights come from `avi_traffic_lights/VIS_TFL_StructElement`.
- SOD/static objects come from `avi_staticobjects/VIS_SOD_Element`.
- TS/TL/CA landmarks are rectangles in ICS and circles in BEV.
- TS text usually includes `[id] sign_name`; supplemental signs may also appear.
- TL text usually includes `[id] traffic light state`.
- SOD/construction/static objects use their own drawing color and labels.

## 8. Final QA Interpretation Procedure
1. Identify the highlighted target in ICS and BEV using row id/object id/class text and the yellow highlight.
2. Read exact numeric values from parsed JSON: distance, velocity, TTC, heading, class, lane assignment, existence probability, and signal delta.
3. Use ICS for visibility, occlusion, edge-of-FOV, object-box quality, and road-scene context.
4. Use BEV for ego-path relevance, lateral/longitudinal position, Road Edge/median/barrier separation, adjacent-lane relevance, and non-drivable-area judgment.
5. Consider road type and driving context from JSON and image: highway/high-speed-road context can raise severity, while parking lot/traffic jam/low-speed maneuvering can lower severity when control impact is limited.
6. Combine JSON and image evidence to decide whether the issue can affect ADAS/AD control logic.

Specific judgment rules:
- For TTC risk, judge TTC together with longitudinal distance, lateral offset, object role, lane assignment, heading/orientation, Road Edge/median separation, and near-field safety impact.
- For TTC/near-object issues, include scene context: high-speed road or fast traffic increases severity; parking lot, stopped traffic, or congestion can reduce severity if the target is not control-critical.
- Raise priority when heading/orientation suggests cut-in, crossing, oncoming conflict, or movement toward the host lane.
- Downgrade only when visual context clearly shows the target is outside the ego drivable corridor or separated by Road Edge, median, barrier, curb, or another non-crossable obstacle.
- For distance or velocity mismatch, use JSON values and deltas as primary evidence, then use BEV to decide whether the mismatch matters for ego control.
- For heading change, judge whether the object is in the relevant ROI and whether the jump affects tracking continuity, cut-in prediction, or trajectory estimation.
- For LiDAR FN, consider whether the LiDAR target is occluded by a nearer object; a far occluded object can be lower priority.
- For LiDAR FP, consider whether the camera object is stable, visible, and high-confidence.
