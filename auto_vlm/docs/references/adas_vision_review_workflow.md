# ADAS Vision Review Workflow

This file is the canonical Auto VLM review workflow for ADAS vision testing.
It defines how a reviewer should inspect raw video, QV overlay, BEV/world-space
rendering, and JSON physical values before assigning feature-level pass/fail.

It is a review workflow, not GT. It explains the evidence order and required
cross-checks for GT-less single-frame review.

## Common 3-Plane Workflow

- First identify real visible targets or road structure in the raw frame; use
  this as scene evidence, not GT accuracy.
- Then inspect the ICS/image overlay to check whether visible scene elements have
  matching drawn outputs, missing outputs, extra outputs, or poor geometry.
- Then inspect BEV/world-space and JSON physical values before clearing
  applicable non-FN/FP issue types.
- Do not stop after ICS looks visually aligned; camera FOV, projection, lens
  distortion, occlusion, and perspective can hide physical-value issues.
- BEV/JSON can reveal issues in long/lat, C0-C3, heading, ID, range, class,
  confidence, state, or other physical values even when ICS looks acceptable.
- A pass requires the applicable issue types to be checked against raw scene,
  ICS overlay, BEV/world-space, and JSON evidence.

## Feature Plane Checklist

### OD

- Inspect visible dynamic objects in the raw center frame before judging OD
  outputs.
- Compare object class, ID/role, ICS bbox/image projection, BEV position,
  long/lat, heading, distance, motion, and JSON summary.
- For DEF-OD-BBOX-DUP, compare both ICS/image boxes and BEV/world-space boxes;
  do not clear an overlap candidate from the ICS view alone.
- Classify only observed object symptoms after considering every OD issue
  family, not only FN/FP or coarse bbox location.

### LD

- Inspect lane-line evidence in the raw center frame before judging LD outputs.
- Compare host_lanes/adjacent_lanes, ICS lane drawing, BEV lane geometry,
  role/type, C0-C3 or polynomial geometry, range, confidence, and drawing_points.
- Do not classify road_edges-only evidence as LD unless lane evidence is also
  involved.

### RBD

- Inspect road-edge or boundary evidence in the raw center frame before judging
  RBD outputs.
- Compare road_edges, ICS boundary drawing, BEV boundary geometry, role/type,
  C0-C3 or polynomial geometry, range, confidence, and drawing_points.
- Do not classify host_lanes/adjacent_lanes-only evidence as RBD unless boundary
  evidence is also involved.

### TS

- Inspect traffic signs in the raw center frame before judging TS outputs.
- Compare traffic_signs/sign-like objects, ICS drawing_rect, BEV/world-space
  position, sign class, supplemental sign, relevancy, confidence, distance, and
  JSON values.
- Classify only observed sign symptoms after considering every TS issue family,
  not only sign count.

### TL

- Inspect traffic lights in the raw center frame before judging TL outputs.
- Compare traffic_lights, ICS drawing_rect/spot, BEV/world-space position,
  state/class, type confidence, distance, and JSON values.
- Classify only observed light symptoms after considering every TL issue family,
  not only light count.

## Must Not

- Do not treat reference documents as GT.
- Do not assign feature or issue type before citing observed raw/QV/JSON
  evidence.
- Do not invent JSON values absent from json_summary or json_snippet.
- Do not treat weak evidence as confirmed SW issue.
- Do not clear a feature only because the ICS/image overlay looks correct;
  inspect BEV/world-space and JSON physical values for applicable issue types.

