# QV Final QA Domain Judgment Guidance

Use this guidance when judging QV rule-detected issues.

## Routing Policy
- Use `uncertain-only` routing by default to save tokens and latency.
- Send rows to LLM only when the evidence is ambiguous: TTC or lateral offset is near the boundary, ROI relevance is unclear, heading-related behavior is involved, tracking continuity is unstable, or image interpretation is needed.
- Do not spend LLM tokens on rows that are already clearly real issues or clearly outside the ego drivable corridor.
- When a row is auto-resolved without LLM, mark it as a conservative pre-judgment and keep the reason explicit.

## Priority Scale And Reporting Obligation
- QV QA must report not only confirmed safety defects but also plausible perception risks that development or project teams should track.
- Treat P1-P3 as reportable issues:
  - P1: severe issue. Use for near-field CIPV, near-field VRU, or adjacent-lane objects when collision risk or ADAS/AD control malfunction is strongly plausible. Do not classify a long-range CIPV as P1 by role alone.
  - P2: important issue. Use for near-field NIV/adjacent-lane issues or slightly farther cases where target selection, cut-in gating, FCW/AEB/ACC, TTC, or trajectory prediction can plausibly be affected.
  - P3: potential issue. Use when the object is farther away or the risk is not certain, but the case is still worth reporting and tracking.
- Treat P4 as currently not an issue but still a customer-visible quality concern or long-term cleanup item. Examples include very far objects around or beyond 120 m, objects beyond guardrail/Road Edge, or cases that are unlikely to affect current control but may be challenged by a customer.
- Treat P5 as not a problem and not meaningful to report.
- Adjacent-position issues should be prioritized conservatively. If the object is close to ego or adjacent lane and the signal jump is lateral distance or lateral velocity, consider higher priority than a pure longitudinal distance jump because lateral instability can affect lane relevance, cut-in prediction, and target selection more directly.

## Ego Path And Drivable Relevance
- A near-field object with severe TTC is not automatically a high-priority issue.
- First judge whether the object is relevant to the ego drivable corridor.
- If the object is outside the host lane, beyond a road edge, behind/over a median, or in a non-drivable region, downgrade priority unless the perception output could affect an ADAS/AD function.
- If a left/right road edge or median separates the object from the ego path, treat the object as likely low priority or not an issue.
- If the object is near the image edge or partially occluded but remains outside the ego path, do not escalate based on TTC alone.

## OD TTC Risk
- Treat TTC as a risk indicator, not a final severity by itself.
- Combine TTC with long distance, lateral distance, lane assignment, road edge/median context, image position, and object kinematics.
- High severity usually requires near-field distance, short TTC, and plausible ego-path overlap.
- If lateral offset is large and the object is outside the drivable corridor, classify as low priority or not an issue even when TTC is short.
- Do not over-downgrade a near-field adjacent-lane large vehicle such as a bus or truck when longitudinal distance, lateral distance, or velocity jumps abruptly. Even if it is not CIPV, it can be misinterpreted by planning/control as a cut-in or near-field collision-risk object.
- For near-field adjacent-lane objects within roughly 30 m longitudinal distance and within about 2.0-3.5 m lateral offset, keep the issue at least medium priority (normally P2-P3).
- If longitudinal distance is within 20 m, treat it as very close and prefer P2 unless a green Road Edge line, median, barrier, or other non-crossable obstacle clearly separates ego and target.
- If the object is an adjacent-lane NIV/bus/truck and the jump could affect FCW/AEB/ACC cut-in gating or target selection, explain that safety-control relevance explicitly instead of reducing directly to P4/P5.
- If a near-field adjacent-lane distance, velocity, or heading jump involves an object heading toward the host lane or ego path, raise priority because trajectory prediction and cut-in gating can become unstable.
- If the same target is clearly parked, stopped, or stationary and BEV/ICS shows it remains outside the ego path, priority can be reduced by one level, but close adjacent-lane dynamic jumps should normally remain P3 unless separated by Road Edge/median/barrier.
- If an oncoming object is separated from the host by a physical barrier, median, green Road Edge line, parked vehicles, or another non-crossable obstacle, downgrade because collision/control relevance is low.
- FSD/free-space is only supporting context. Do not use FSD termination alone as a downgrade reason because FSD can naturally stop at vehicles, pedestrians, or obstacles.
- For adjacent-lane oncoming vehicles with longitudinal distance jumps, keep at least P2 when the object is close and the issue occurs beside ego. If the scenario appears to be a dark underpass or bridge-shadow condition, note it as a condition-specific perception weakness and usually keep P2 rather than P1.
- If a comparable adjacent-lane case has lateral distance or lateral velocity jumping instead of only longitudinal distance, consider P1 when it can directly disturb ego-path relevance or ADAS control.
- For city/intersection cases, a near adjacent-lane bus or large vehicle with about a 5 m lateral-distance jump is normally P2: reportable and important, but usually not P1 unless the object is entering ego path or high-speed control impact is likely.

## OD Heading Change
- For Heading Change, explicitly compare previous heading, current heading, and delta when values are available.
- A near cyclist/VRU heading jump can become P1-P2 if the target is directly in front of ego or likely to enter ego path.
- If the cyclist/VRU is close but has meaningful lateral offset and does not appear directly in ego path, P3 is acceptable because it is still a potential issue but not an immediate control hazard.

## Image Review
- Use issue screenshots to check whether the object is in ego lane, adjacent lane, outside road edge, behind a barrier/median, or at edge-of-FOV.
- Mention road edge, median, ego lane, adjacent lane, non-drivable area, and occlusion when they affect the final judgment.
- Screenshot layout:
  - Left side is the original camera/ICS view with JSON perception drawing and LiDAR drawing when available.
  - Right side is the BEV (bird's-eye view) generated from logs.
  - The issue target is highlighted in yellow when available.
  - In ICS, the issue target is usually marked with a yellow bounding box.
  - In BEV, the issue target is usually marked with a yellow circle.
  - Highlight may be missing in either view, so use JSON context as the stable source of target id/signals.
- Use ICS primarily for visibility, occlusion, edge-of-FOV, bounding-box quality, and whether the highlighted object is visually plausible.
- Use BEV primarily for ego-path relevance, lane/green Road Edge line/median separation, adjacent-lane relevance, non-drivable area, and whether the highlighted object can affect host vehicle behavior.

## Feedback From Reviewer
- Reviewer noted that an object on the host vehicle's left side may be outside a detected road edge/median.
- Such an object can be outside the area the host vehicle can cross into, so it may be not an issue or low-priority despite a TTC rule trigger.
- Reviewer noted that near-field adjacent-lane large-object jumps can still be meaningful because the controller may temporarily interpret the object as a cut-in or collision-risk candidate.
- Reviewer prefers Korean-only narrative in the final Excel, with English abbreviations limited to standard acronyms only.
- Reviewer defined the reporting-oriented priority scale: P1-P3 are reportable issues, P4 is not a current issue but should be cleaned up eventually, and P5 is not a problem.
- Reviewer feedback from `20260513_212608_input_yaml_fvc_llm_final_qa_20260513_215010.xlsx`:
  - Rows 1-2: adjacent-lane bus in a city/intersection scenario with about 5 m lateral-distance jump should be P2. It is close and reportable; P1 may be considered for lateral signal jumps in higher-risk/high-speed or ego-path-entering contexts.
  - Row 3: close cyclist heading jump with some lateral offset can remain P3 unless the cyclist is directly in front of ego or moving into ego path.
  - Rows 4-5: adjacent-lane oncoming vehicle longitudinal-distance jump should be at least P2. Dark bridge/underpass context suggests condition-specific weakness, so keep P2 rather than P1. Lateral distance or lateral velocity jumps in a similar adjacent-lane case could justify P1.
