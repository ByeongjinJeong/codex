# Context Evidence Requirement Notes

## Current Decision

Context strip evidence is disabled in the active workflow.

The current Auto VLM pipeline should focus on judging one sampled frame well before
adding adjacent-frame context back into the review packet. Context images can be
useful, but the existing strip format made each frame smaller and harder to inspect.
For small or detailed evidence such as traffic signs, traffic lights, lane geometry,
and bounding boxes, this can reduce review quality instead of improving it.

## Why Context Was Removed For Now

The previous approach generated a horizontal context strip around each sampled
frame using offsets such as:

```text
-5, -2, 0, +2, +5
```

For sampled frame `100`, the context strip visually combined:

```text
95 | 98 | 100 | 102 | 105
```

This had several issues:

- Each frame became smaller in the combined image.
- Human inspection was already difficult, which implies VLM inspection is also weak.
- The model could over-trust low-detail context thumbnails.
- The sampled-frame JSON only represented frame `100`, not the adjacent frames.
- The prompt could accidentally encourage comparing adjacent overlay frames against
  the sampled-frame JSON.

## Current Active Evidence Scope

The active review packet should use:

```text
1. raw center frame
2. QV overlay center frame
3. sampled-frame JSON snippet
4. sampled-frame JSON summary
5. evidence integrity flags
6. feature-specific review context
```

The VLM should treat the sampled frame as the only frame under review.

## Important JSON Policy

Adjacent context frames must not be compared against the sampled-frame JSON unless
the pipeline explicitly loads and labels JSON for each adjacent frame.

If frame `100` is the sampled frame:

```text
Allowed now:
  frame 100 raw image
  frame 100 QV overlay image
  frame 100 JSON

Not allowed now:
  comparing frame 95 overlay to frame 100 JSON
  comparing frame 98 overlay to frame 100 JSON
  comparing frame 102 overlay to frame 100 JSON
  comparing frame 105 overlay to frame 100 JSON
```

## When Context Should Be Reintroduced

Context evidence should be reintroduced only after center-frame judgment quality is
acceptable.

Good reasons to reintroduce context:

- OD flicker checks
- object update failure
- ID switch or duplication
- sudden value jump confirmation
- overlay/raw synchronization suspicion
- temporal stability checks requested by the user

Weak reasons to reintroduce context:

- basic object existence judgment
- traffic sign class reading
- traffic light color/state reading
- lane or road boundary geometry judgment from a small strip

## Recommended Future Design

Do not return to the old strip-only design as the main evidence.

Preferred future approach:

```text
Primary evidence:
  sampled raw center frame at original resolution
  sampled QV overlay center frame at original resolution
  sampled-frame JSON

Optional temporal evidence:
  separate adjacent frame images, not one compressed strip
  clearly labeled frame numbers
  optional adjacent-frame JSON per frame
  explicit prompt rule that temporal context is secondary

Optional detail evidence:
  crop images for OD bbox, TS sign, TL light, or suspicious lane/edge regions
```

Suggested context modes:

```text
mode=off
  No adjacent-frame evidence. Current default.

mode=images_only
  Adjacent raw/QV images are shown only for temporal continuity.
  No adjacent JSON comparison is allowed.

mode=images_and_json
  Adjacent raw/QV images and adjacent JSON snippets are loaded per frame.
  Each frame must be labeled and compared only to its own JSON.
```

## Prompt Rule For Future Context

If context is added again, the prompt must include this rule:

```text
The sampled frame is the primary review target.
Adjacent context frames are secondary temporal evidence only.
Do not compare an adjacent frame against the sampled-frame JSON.
Only compare a frame to JSON that is explicitly labeled with the same frame number.
```

## Current Implementation Note

As of this decision, active pipeline generation should not create:

```text
qv_context/
raw_context/
*_context.jpg
```

Existing report columns may remain for backward compatibility, but new runs should
leave context paths empty unless context support is intentionally re-enabled.
