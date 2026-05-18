---
name: regression-automation-tool
description: Use for the Regression_automation_tool repository when the user asks Codex to process Issue_Request_aptiv.xlsx, add customer Jira issues for APTIV regression testing, update Input_Management_aptiv.xlsx, add Config_tc_aptiv.py rule mappings, generate target-matching reference JSON, or infer Rule base regression setup from Jira/user hints and frame ranges. This is chat-first; do not require the user to run a CLI or provide Jira API access.
---

# Regression Automation Tool

Use this skill only when the current task concerns:

- the `Regression_automation_tool` repository
- Adding customer Jira issues to the regression automation workflow
- Updating APTIV regression issue inputs, reference rows, rule mappings, or related rule/config code

## User Interface

The primary interface is `Issue_Request_aptiv.xlsx` / `Issue Queue`.
Process rows whose `STATUS` is `이슈추가`.

Request workbook columns:

- `STATUS`
- `ISSUE_ID`
- `JIRA_TICKET`
- `USER_HINT`
- `FRAME_START`
- `FRAME_END`
- `TRACK_ID_OR_LANE`
- `JSON_PATH`
- `VIDEO_PATH`
- `NOTES`
- `CODEX_RESULT`
- `CODEX_ANALYSIS_LOG`
- `UPDATED_AT`

Do not ask the user to run a CLI. If a helper script exists later, treat it as a Codex-internal aid.

## Core Workflow

1. Read repo context:
   - `AGENTS.md`
   - `docs/WORK_UNITS.md` and `docs/SESSION_HANDOFF.md` if present
   - `git status --short`
2. Parse the user input:
   - issue ID
   - Jira ticket key from `JIRA_TICKET` when present
   - free-text user context from `USER_HINT` and `NOTES`
   - frame range
   - paths, track IDs, thresholds, or SW versions if supplied
   - if using `Issue_Request_aptiv.xlsx`, read each `이슈추가` row and preserve user-provided paths
   - if Jira access is available, fetch/review `JIRA_TICKET` first; fall back to `ISSUE_ID` only when `JIRA_TICKET` is blank
3. Inspect existing project patterns before deciding:
   - Similar issue rows in `Input_Management_aptiv.xlsx`
   - Similar rule mappings in `Config/Config_tc_aptiv.py`
   - Existing rule/reference dispatch functions
4. Validate inferred signal/attribute names against the actual user-provided JSON before finalizing rule mappings:
   - Open representative files from `JSON_PATH` for the requested frame range when accessible.
   - Treat user-provided feature/signal wording as approximate hints; the user may not know the exact JSON key.
   - Confirm the final signal name written into the rule criteria exists in raw JSON, `Config/Config_setting.py` aliases, or preprocessed output.
   - If the inferred final signal cannot be found in the actual JSON/preprocessed output, mark the row `검토중` and explain the missing signal instead of guessing.
   - For LD/RBD polynomial range rules (`LD_RBD_Localization`, `LD_RBD_CPP`, `LD_RBD_C0`, `LD_RBD_C1_C2`, `LD_RBD_C1`, `LD_RBD_C2`), derive numeric criteria from the request row's actual JSON output for the requested frame range and target lane/road edge. Similar issues may define the rule shape, but do not reuse their numeric range unless the actual JSON output supports it.
5. Infer the regression setup:
   - feature
   - final method, normally `Rule base`
   - issue type
   - data attributes
   - reference JSON generation need for target matching
   - rule mapping or code changes
   - whether manual ICS bbox reference patching is needed because no GT/reference exists
6. Ask only for missing information that cannot be inferred safely.
7. Apply changes only after understanding current user edits and expected impact.
8. If reference rows were added or remain `NOT READY`, run `python Extract_Reference.py` and use the generated target-matching reference output path.
9. If manual bbox reference patching is needed, patch only the generated `filter_json` files after `Extract_Reference.py`:
   - map user/object ICS rect coordinates to the target feature's parser keys
   - preserve the user's rectangle semantics
   - create one reference object per supplied rectangle unless explicitly told otherwise
   - generate a debug overlay when a video path is available
10. If input/config changes are complete and paths are accessible, run `python Execute_TC.py` to verify the regression setup.
11. Verify and summarize changed files.

## Issue Request Workbook Workflow

For `Issue_Request_aptiv.xlsx`:

1. Process only rows with `STATUS = 이슈추가`.
2. Before editing regression files, mark the row as `검토중` with `CODEX_RESULT = 처리중: <timestamp>`.
3. Treat every user-entered request row as a new issue-add request keyed by `JIRA_TICKET` when present; otherwise use `ISSUE_ID`.
4. Do not skip a request only because a similar issue exists. Use similar issues only as inference references.
5. If an existing row/mapping would be overwritten or the exact target key is ambiguous, mark `검토중` and explain the conflict in `CODEX_RESULT`.
6. If `STATUS = 검토요청` or `NOTES` contains `prepare only`, write proposed changes and analysis only; do not edit regression files.
7. Most requests should evaluate by `Rule base`. Generate/reference JSON when needed to match the target, but use that reference output as rule input evidence rather than choosing final `Reference` evaluation, unless direct reference comparison is explicitly required and valid GT/reference criteria exist.
8. On success, write:
   - short summary to `CODEX_RESULT`
   - Korean reviewer-facing reasoning to `CODEX_ANALYSIS_LOG`
   - timestamp to `UPDATED_AT`
   - `STATUS = 완료`

Required request fields for new datasets:

- `ISSUE_ID`
- `FRAME_START`
- `FRAME_END`
- `TRACK_ID_OR_LANE`
- `JSON_PATH`
- `VIDEO_PATH`

If Jira is unavailable and `USER_HINT` / `NOTES` are too vague to classify the issue, mark `검토중` and ask for a clearer symptom description.

## Jira Usage

When a Jira MCP or connected Jira search is available:

- Fetch the issue by `JIRA_TICKET` when present; otherwise fall back to `ISSUE_ID`.
- Use Jira title/description/comments as the main issue content.
- Use request workbook `USER_HINT` and `NOTES` as supplements or overrides.
- Record in `CODEX_ANALYSIS_LOG` that Jira content was reviewed.
- Use Jira in read-only mode only.
- Never add Jira comments.
- Never edit Jira fields.
- Never transition Jira status.
- Never create Jira issues.

If Jira lookup fails, continue only when the request row still has enough information to infer the setup safely.

## Korean Analysis Log Requirements

`CODEX_ANALYSIS_LOG` must be understandable to a reviewer who has never seen the issue.

Include these sections:

- `[이슈 원문 검토]`: Jira/user input summary and plain-language symptom interpretation.
- `[Feature 분류]`: selected feature and why.
- `[Issue Type 분류]`: selected issue type and symptom/similar-issue basis.
- `[Test Method 선정]`: why final evaluation is `Rule base`, or why a rare direct `Reference` evaluation is required.
- `[Signal 검증]`: approximate user wording, checked JSON/preprocessed key, and final rule signal name.
- `[Rule 선정]`: exact rule mapping selected; if reference JSON was generated, explain it is for target matching.
- `[Criteria 선정 근거]`: threshold/criteria logic; explain `None` when no criteria is needed.
- `[추가/수정 내용]`: Excel/config/code changes.
- `[검증]`: request-key handling, reference-json handling, readback, and syntax verification.

## Files That May Be Edited

Default issue-add work may edit:

- `Input_Management_aptiv.xlsx`
- `Issue_Request_aptiv.xlsx`
- `Config/Config_tc_aptiv.py`

Code changes are allowed when existing rules/config cannot express the issue:

- `Function Script/*`
- `Config/Config_setting.py`

Minimize code edits. Before changing rule or config code, state why existing mappings/functions are insufficient.

## Safety Rules

- Never revert user changes.
- Always check `git status --short` before editing.
- Do not treat user-entered request rows as duplicates to skip; the user curates this workbook.
- Make request workbook processing idempotent for the same request row; retries must continue partial work without adding another request row.
- Jira is read-only evidence. Do not use Jira write tools even if they are available.
- Prefer existing patterns over new abstractions.
- Keep questions minimal and concrete.
- If editing Excel, preserve workbook structure and formulas/styles as much as practical.
- If editing Python config/rules, run relevant syntax checks.

## References

Read these only as needed:

- `references/project-map.md` for project file map, Excel sheets, and execution flow.
- `references/inference-rules.md` for feature/method/rule inference and question thresholds.

## Expected Output

When finishing a task, report:

- what issue was added or prepared
- files changed
- inferred feature/method/issue type/rule
- questions asked or assumptions made
- verification performed
- any remaining manual data needed
