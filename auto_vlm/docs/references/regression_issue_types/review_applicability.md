# Review Applicability for GT-less Single-Frame Runs

This file is the canonical review-mode policy for Auto VLM's current primary mode:
one sampled frame, raw image, QV overlay image, and JSON output, without GT.

Status values:
- `direct`: can be evaluated from the current frame's raw/QV/JSON evidence.
- `limited`: can be screened for obvious symptoms, but not fully proven without temporal, reference, or GT evidence.
- `not_evaluable`: should not be judged pass/fail in this mode; mark as not evaluable and explain the missing evidence.

Future review modes, such as LiDAR-GT JSON or frame-range review, should add a new
status column instead of changing the meaning of this GT-less single-frame column.

```text
feature | issue_type | gtless_single_frame | reason
OD | DEF-OD-FN | limited | Obvious visible missed objects can be suspected, but full FN needs reference/GT or frame-range context.
OD | DEF-OD-FP | limited | Obvious ghost objects can be suspected, but full FP needs reference/GT or stronger scene confirmation.
OD | DEF-OD-BBOX-FIT | direct | Raw object shape can be compared with QV image-space bbox/projection.
OD | DEF-OD-BBOX-DUP | direct | Duplicate/split boxes can be checked from QV overlap and JSON object IDs in the sampled frame.
OD | DEF-OD-DIST-LONG | not_evaluable | Metric longitudinal distance needs GT/reference or calibrated measurement beyond visual plausibility.
OD | DEF-OD-DIST-LAT | not_evaluable | Metric lateral distance needs GT/reference or calibrated measurement beyond visual plausibility.
OD | DEF-OD-VELOCITY | not_evaluable | Velocity cannot be judged from one discrete frame without temporal/GT evidence.
OD | DEF-OD-ACCEL | not_evaluable | Acceleration cannot be judged from one discrete frame without temporal/GT evidence.
OD | DEF-OD-HEADING | limited | Coarse orientation can be checked visually, but exact heading angle needs reference/temporal context.
OD | DEF-OD-MOTION | limited | Coarse stationary/moving cues may be visible, but motion status is weak from one frame.
OD | DEF-OD-CLASS | direct | Object class can often be compared between raw object appearance and overlay/JSON class.
OD | DEF-OD-ID | not_evaluable | ID switch/consistency requires temporal frame-range evidence.
OD | DEF-OD-DATA-UPDATE | not_evaluable | Update failure/staleness requires temporal frame-range evidence.
LD | DEF-LD-RBD-FN | limited | Obvious missing visible lane lines can be suspected, but full FN needs reference/range context.
LD | DEF-LD-RBD-FP | limited | Obvious non-lane overlays can be suspected, but full FP needs reference/range context.
LD | DEF-LD-RBD-RANGE | limited | Range can only be visually screened, not measured strictly, without reference/GT.
LD | DEF-LD-RBD-LOCALIZATION | direct | Lane overlay geometry can be compared with raw lane markings.
LD | DEF-LD-RBD-CPP | not_evaluable | CPP requires path/reference semantics not available from one frame alone.
LD | DEF-LD-RBD-COEFF | not_evaluable | Polynomial coefficient correctness needs numeric reference/GT.
LD | DEF-LD-RBD-TYPE | direct | Lane type/class can be compared with visible markings when visible.
LD | DEF-LD-RBD-ROLE | limited | Left/right/host/adjacent role can be screened, but ambiguous layouts may need context.
LD | DEF-LD-RBD-UPDATE | not_evaluable | Update/staleness requires temporal frame-range evidence.
RBD | DEF-LD-RBD-FN | limited | Obvious missing road edges/boundaries can be suspected, but full FN needs reference/range context.
RBD | DEF-LD-RBD-FP | limited | Obvious non-boundary overlays can be suspected, but full FP needs reference/range context.
RBD | DEF-LD-RBD-RANGE | limited | Range can only be visually screened, not measured strictly, without reference/GT.
RBD | DEF-LD-RBD-LOCALIZATION | direct | Boundary overlay geometry can be compared with visible curbs/medians/barriers.
RBD | DEF-LD-RBD-CPP | not_evaluable | CPP requires path/reference semantics not available from one frame alone.
RBD | DEF-LD-RBD-COEFF | not_evaluable | Polynomial coefficient correctness needs numeric reference/GT.
RBD | DEF-LD-RBD-TYPE | limited | Boundary type/class can be screened when the boundary is visible.
RBD | DEF-LD-RBD-ROLE | limited | Left/right/boundary role can be screened, but ambiguous layouts may need context.
RBD | DEF-LD-RBD-UPDATE | not_evaluable | Update/staleness requires temporal frame-range evidence.
TS | DEF-TS-FN | limited | Obvious visible missed signs can be suspected, but full FN needs reference/GT.
TS | DEF-TS-MISCLASS | direct | Sign class can be compared when the sign face is readable.
TS | DEF-TS-FP | limited | Obvious ghost sign outputs can be suspected, but full FP needs reference/GT.
TS | DEF-TS-FP-DUP | direct | Duplicate sign outputs in one visible/reference region can be screened in one frame.
TS | DEF-TS-ID-RANGE | not_evaluable | ID range/consistency requires temporal frame-range evidence.
TS | DEF-TS-DIST-LONG | not_evaluable | Metric sign distance needs GT/reference.
TS | DEF-TS-SHAPE | direct | Sign shape can be compared when visible.
TS | DEF-TS-MEASUREMENT | not_evaluable | Measurement status/update requires rule/reference semantics and often temporal evidence.
TS | DEF-TS-AGE-IMAGE | limited | In-image/out-of-image can be screened visually; age needs temporal evidence.
TL | DEF-TL-FN | limited | Obvious visible missed traffic lights can be suspected, but full FN needs reference/GT.
TL | DEF-TL-FP | limited | Obvious ghost TL outputs can be suspected, but full FP needs reference/GT.
TL | DEF-TL-DIST-LONG | not_evaluable | Metric TL distance needs GT/reference.
TL | DEF-TL-STATE | not_evaluable | State sequence requires temporal frame-range evidence.
TL | DEF-TL-SPOT | direct | Spot color/shape can be compared when the light is visible and resolvable.
```
