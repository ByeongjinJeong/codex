# Inference Rules

Use existing project rows and mappings as the primary source of truth. These rules guide first-pass inference, not blind application.

## Operating Principle

For any chat request, infer a complete candidate setup before editing:

1. Identify issue ID, Jira ticket key if different, user hint text, frame range, and any supplied track/lane/path/threshold/SW version.
2. Search similar rows/mappings by feature, issue type, keywords, and nearby issue IDs for inference reference.
3. Treat each user-entered request row as a new issue-add request keyed by `JIRA_TICKET` when present; otherwise by `ISSUE_ID`.
4. Validate candidate signal/attribute names against the actual user-provided JSON and preprocessed output.
5. Decide whether the issue is:
   - an Excel-only addition
   - an Excel + `tc_rules_mapping` addition
   - a code-change issue because no existing rule/reference path can express it
6. Ask one focused question only if the candidate setup is still unsafe.

Do not skip a user-entered request only because a similar issue exists. Similar issues are references for feature, issue type, criteria, and rule selection.

For `Issue_Request_aptiv.xlsx`, make processing idempotent:

- Mark a row `검토중` with a timestamp before editing regression files.
- On retry, continue the same request row and reconcile partial work already written for that row.
- If existing data would be overwritten or the target key is ambiguous, leave the row `검토중` and explain the conflict.

When Jira text is available, use it as the primary issue description. Fetch Jira by `JIRA_TICKET` when present; otherwise fall back to `ISSUE_ID`. Use request workbook `USER_HINT` and `NOTES` as supplements.

Most customer issues lack GT for direct reference-method evaluation. Default to `Rule base` evaluation. Generate or configure reference JSON when needed to match the issue target, then use the reference output as rule input evidence. Choose final `Reference` evaluation only when direct reference comparison is explicitly required and the needed GT/reference criteria are available.

## Signal Name Validation

Before writing or finalizing `Config/Config_tc_aptiv.py` rule criteria that contain a signal/attribute name, validate the inferred final name using the user's actual `JSON_PATH`.

The user may provide only approximate feature/signal wording. Do not require the user to know the exact JSON key. Use their wording as a search hint, then inspect the actual JSON/preprocessor output to choose the canonical rule key.

Required process:

1. Resolve the request row's `JSON_PATH` using the same parent-path convention as `Execute_TC.py` when the workbook stores relative paths.
2. Open representative JSON files from the requested frame range when accessible.
3. Use the user's wording, Jira wording, feature name, and similar rows only as search hints.
4. Confirm that the final rule key you plan to write is present in one of: raw JSON keys, `Config_setting.py` aliases, or preprocessed records for the target feature.
5. Record the checked key and final rule key in `CODEX_ANALYSIS_LOG` under `[Signal 검증]`.

Do not rely only on Jira wording, `USER_HINT`, or a similar issue row for the exact signal name. Similar rows are hints; the actual JSON/preprocessor output is authoritative.

If the user's approximate signal appears under a different raw JSON name, use the canonical preprocessed key expected by the rule and note the alias. If the inferred final signal is not present in raw JSON, config aliases, or preprocessed output, stop before adding a guessed mapping: leave the request `검토중` and write the missing signal evidence in `CODEX_RESULT`.

## Feature Hints

- `TSR`, `traffic sign`, `sign`, `speed limit` -> `TS`
- `OD`, `object`, `pedestrian`, `vehicle`, `car`, `bbox` -> `OD`
- `LD`, `lane` -> `LD`
- `RBD`, `road boundary` -> `RBD`
- `CA`, `construction area` -> `CAO` or `CAO_HEADER` based on similar rows
- `RMD`, `road marking` -> `RMD_SM` or `RMD_SL` based on similar rows
- `calib`, `calibration` -> `CALIB`
- `common`, image quality, blockage, blur, sun -> `COMMON` unless similar rows show otherwise

Strong feature mappings:

- APTIV TSR wording almost always maps to workbook feature `TS`.
- Traffic light/TFL wording maps to `TL`.
- Lane line, road edge, or boundary wording must be split into `LD` versus `RBD` by similar rows or by the described object.
- Road marking wording must be split into `RMD_SM` versus `RMD_SL`; ask if similar rows do not decide it.

## Method Selection

Prefer `Rule base` when:

- The issue can be checked by a deterministic signal/range/jump/update/fn/fp rule.
- A similar issue already exists in `Config/Config_tc_aptiv.py`.
- The user description names a signal-like attribute such as `Tracking_ID`, `Heading`, `Dis_Lat`, `Vel_Rel_Lat`, `C0`, `C1`, `C2`.
- The issue needs reference JSON only to isolate or match the target, while the pass/fail decision is still a deterministic rule.
- The request resembles known APTIV customer issue mappings such as:
  - TS tracking ID jump/new ID -> `ts.TS_VALUE_JUMP`
  - TS missing / lost target -> `ts.TS_FN`
  - OD distance or velocity range -> `od.OD_RANGE_VALIDITY`
  - OD value jump -> `od.OD_VALUE_JUMP`
  - OD heading jump -> `od.OD_HEADING_ANGLE_JUMP`
  - LD/RBD C0/C1/C2/range/FN/FP -> matching `ld.LD_RBD_*` rule

Generate or configure reference JSON for target matching when:

- The check requires a curated target object/sign/lane over a frame range.
- Track ID/lane is central to evaluation.
- The user supplies or can clearly infer a frame range and track ID/lane for reference extraction.
- A close precedent has paired `Reference Management` rows for the same type of target selection.

Keep the final method as `Rule base` after target matching unless direct reference comparison is explicitly required and valid GT/reference criteria are available.

Choose final `Reference` evaluation only when:

- Jira or the user explicitly asks for direct comparison against curated reference results.
- The required GT/reference criteria are available and express the actual pass/fail semantics.
- Existing reference dispatch tables cover the feature and issue type without changing the intended meaning.

Ask when:

- Both methods are plausible and similar examples conflict.
- Reference mode needs a track ID/lane that cannot be inferred.
- Rule mode needs a threshold not found in similar issues.
- The user supplied only an issue ID and title, with no paths and no similar row to copy paths from.

Method conflict rule:

- If a similar issue in `TC Management` uses `Rule base`, prefer `Rule base` even when a `Reference Management` row exists. Existing rows often keep reference data for GT/filter setup while the actual test method is rule-based.
- If no `tc_rules_mapping` exists, first check whether an existing deterministic rule can express the issue and add a mapping if appropriate. Do not choose final `Reference` only because `Evaluation_Reference.py` has a dispatch entry.

## Issue Type Hints

- `not detected`, `missing`, `lost`, `not tracked when leaving FOV` -> `FN` or a tracking-specific rule depending on similar rows.
- `false positive`, `ghost`, `extra detection` -> `FP`
- `misclassification`, `classified as`, `wrong class` -> `Misclassification`
- `new id`, `id change`, `tracking id`, `id switch`, `dropped and detected again` -> `ID Range`, `TS_VALUE_JUMP`, or ID consistency rule based on feature and examples.
- `jump`, `flicker`, `sudden change` -> value jump or update/flicker rule.
- `heading`, `angle` -> heading angle/range rule.
- `distance lat`, `lateral distance` -> `Dis_Lat` range/validity rule.
- `velocity rel lat` -> `Vel_Rel_Lat` range/validity rule.

Recommended Rule base mappings:

- TS:
  - missing / lost / not tracked -> `['ts.TS_FN', None]`
  - new ID / ID changes / dropped then detected again -> `['ts.TS_VALUE_JUMP', (<threshold>, 'Tracking_ID', 'Traffic Sign tracking ID')]`
  - update failure -> `['ts.TS_Update_Failure', (...)]` only if similar examples define the criteria shape
  - value range -> `['ts.TS_VALUE_RANGE_CHECK', (...)]` only after checking examples
  - ID consistency -> `['ts.TS_ID_CONSISTENCY', (...)]` only if the expected consistency pattern is clear
- OD:
  - false negative -> `['od.OD_FN', <threshold>]`
  - false positive -> `['od.OD_FP', <threshold>]`
  - value jump -> `['od.OD_VALUE_JUMP', (<delta>, '<attribute>', '<label>')]`
  - heading jump -> `['od.OD_HEADING_ANGLE_JUMP', <degrees>]`
  - range/validity -> `['od.OD_RANGE_VALIDITY', (<min>, <max>, '<attribute>', '<label>', <inclusive_or_bool>)]`
  - update failure -> `['od.OD_Update_Failure', ('<attribute>', [invalid_values...])]`
  - ID switch/duplication -> `od.OD_ID_Switch` or `od.OD_ID_Duplication` based on existing examples
- LD/RBD:
  - FN -> `['ld.LD_RBD_FN', None]`
  - FP -> `['ld.LD_RBD_FP', None]`
  - range -> `['ld.LD_RBD_RANGE', (<range>, '<more than|less than>')]`
  - C0/C1/C2 -> matching `ld.LD_RBD_C0`, `ld.LD_RBD_C1`, `ld.LD_RBD_C2`, or `ld.LD_RBD_C1_C2`
  - polynomial combinations -> `ld.LD_RBD_CPP` when examples match the required tuple shape

Recommended Reference issue types:

- OD: use exact issue types from `OD_DISPATCH_TABLE`.
- LD/RBD: use `FN`, `FP`, `Range`, `Type class`, or `C0`.
- TS: use `FN`, `Misclassification`, `FN+Misclassification`, `FN+Misclassification+Sup1`, `Misclassification+Sup1`, or `Shape`.
- TL: use `FN` or `FN+Misclassification`.

If the inferred issue type is not exactly accepted by the target path, either map to a known accepted name or ask before inventing a new one.

## Excel Row Inference

For `TC Management` additions:

- Copy path style, status, business value, resolution, and attributes from the closest similar issue when available.
- Use the new issue ID in column B.
- Use inferred method, feature, and issue type in columns C:E.
- Use reference path convention:
  - Prefer the actual `Extract_Reference.py` output path, typically `\\10.20.20.230\nqa\Project\APTIV\04_Tool\Reference_GT_customer\<ISSUE_ID>\filter_json`.
  - Preserve the case and prefix style from the generated output or nearby rows when copying.
- JSON/video row paths are usually relative to workbook fixed Coco6 parent paths.
- For TS/OD tracking-related rule rows, column O (`ATTRIBUTE 1`) is often the signal such as `Tracking_ID`.

For `Reference Management` additions:

- Add a row when reference JSON must be generated or when a strong similar issue has a paired reference row.
- Use status `NOT READY` when new reference output still needs generation.
- Use status `READY` only when the reference output is already present or copied from a known completed setup.
- Required data:
  - issue ID
  - feature type
  - start frame
  - end frame
  - track ID or lane
  - base SW version
  - video file name
  - raw JSON path
- Ask for track ID/lane if neither user input nor similar rows provide it.
- Ask for raw JSON path if no similar issue supplies a path and the workbook fixed cells cannot derive it.

## Threshold Inference

Thresholds may be inferred only from close precedent:

- Same feature.
- Same issue mechanism.
- Same attribute.
- Similar title/description.

Examples:

- `TS_VALUE_JUMP` for `Tracking_ID` can reuse `0.5` when matching the existing `FXE-1509` pattern.
- `TS_FN` needs no criteria.
- OD/LD numeric thresholds must be copied from a close row or asked for.

If a threshold affects pass/fail semantics and no close precedent exists, ask instead of guessing.

## When Code Edits Are Allowed

Editing `Function Script/*` or `Config/Config_setting.py` is allowed only when:

- No existing rule function or reference dispatch can express the issue.
- A required signal/attribute mapping is missing.
- The issue needs a new reusable evaluation rule.

Before such edits:

1. Identify the closest existing rule or dispatch table.
2. Explain why it is insufficient.
3. Keep the change scoped to the relevant feature/rule module.
4. Run syntax checks after editing.

Prefer no code edits when one of these is enough:

- Adding a `tc_rules_mapping` entry to `Config/Config_tc_aptiv.py`.
- Adding TC/Reference rows to `Input_Management_aptiv.xlsx`.
- Mapping the request to an existing reference dispatch issue type.

Code edit destinations:

- New deterministic rule: edit only the relevant `Function Script/Rule_Function/Rule_*.py`, then add mapping in `Config/Config_tc_aptiv.py`.
- New reference issue type: edit `Function Script/Evaluation_Reference.py` dispatch table and the relevant `Reference_Function/Ref_*.py`.
- Missing signal mapping or threshold constant: edit `Config/Config_setting.py`.

## Minimum Questions

Ask at most one focused question at a time when blocked. Common questions:

- "Which track ID or lane should be used for the reference row?"
- "What JSON/video path should this issue use?"
- "What threshold should this rule use? I found no close precedent."
- "Should this be treated like existing issue FXE-____?"

Do not ask for fields that can be copied from a strong similar issue pattern.

Confidence thresholds:

- 90%+ confidence: apply directly after request-key/status checks.
- 70-89% confidence: apply only if the uncertain field is non-critical or copied from a very close pattern; otherwise ask.
- Below 70% confidence: ask one focused question.

Critical fields that normally require high confidence:

- track ID/lane
- raw JSON path
- rule signal/attribute name verified against actual JSON/preprocessed output
- pass/fail threshold
- final `Reference` evaluation when it would change pass/fail semantics from the default `Rule base`
- new code behavior

## Validation Checklist

Before applying:

- Check `git status --short`.
- Confirm the request key (`JIRA_TICKET`/`ISSUE_ID`) and ensure the intended row/mapping will not overwrite unrelated existing data.
- Compare against at least one similar issue row or mapping when possible.
- Validate any rule signal/attribute names against the actual user-provided JSON path and relevant preprocessor output.
- Confirm workbook sheet names and row start conventions before editing Excel.
- If editing Excel, preserve styles/formulas by copying from the closest similar row when practical.
- If editing Python, preserve existing mapping format and keep user edits.
- If processing `Issue_Request_aptiv.xlsx`, preserve the user-provided JSON/video paths and write final reasoning to `CODEX_ANALYSIS_LOG`.

After applying:

- Summarize Excel rows added or changed.
- Summarize Python mappings/functions changed.
- Run `python Extract_Reference.py` when new or pending `Reference Management` rows need target-matching JSON.
- Run `python Execute_TC.py` when the workbook/config changes are complete and the required paths are accessible.
- Run `python -m py_compile Config/Config_tc_aptiv.py` if that file changed.
- Run syntax checks for any edited rule/config Python files.
- Re-read the affected Excel rows or Python mappings to confirm the intended issue ID appears exactly once.

## Korean Request Log

For request workbook rows, `CODEX_ANALYSIS_LOG` must include:

- `[이슈 원문 검토]`
- `[Feature 분류]`
- `[Issue Type 분류]`
- `[Test Method 선정]`
- `[Signal 검증]`
- `[Rule 선정]`
- `[Criteria 선정 근거]`
- `[추가/수정 내용]`
- `[검증]`

Write the log for a reviewer who has not seen the issue before. Explain the symptom, classification, selected rule/reference path, criteria reasoning, and verification in Korean.

## Known Example Pattern

`FXE-1509` / `FXE-1510` establish the current TSR pattern:

- Both use feature `TS`.
- Both use method `Rule base`.
- Both have paired `Reference Management` rows for frame `300` to `340`, track ID `10`, and the same raw JSON path.
- `FXE-1509`: "Dropped classified SL sign is detected again with a new id"
  - issue type: `ID Range`
  - attribute 1: `Tracking_ID`
  - mapping: `['ts.TS_VALUE_JUMP', (0.5, 'Tracking_ID', 'Traffic Sign tracking ID')]`
- `FXE-1510`: "Traffic sign is not tracked when leaving field of view"
  - issue type: `FN`
  - attribute 1: `Tracking_ID`
  - mapping: `['ts.TS_FN', None]`

For future TSR requests with similar wording and the same dataset, prefer this pattern unless the user supplies a different track ID, frame range, path, or intended method.
