---
name: qv-issue-html-review
description: >-
  Generate a browser-friendly HTML review report from a Qualification Visualizer
  QA Excel file and linked issue screenshots. Use when a user wants to inspect
  issue rows visually in HTML before final judgment.
---

# QV Issue HTML Review

## Workflow
1. Read the QV QA Excel output.
2. Prefer the `최종검토` sheet, then fall back to `qa_review`, `issues_with_llm`, or the first sheet.
3. Merge `기술컨텍스트` when present so image paths and routing metadata are preserved.
4. Resolve screenshots from:
   - explicit image-path columns in the workbook
   - the sibling `<excel_stem>/` image folder
5. Render a single HTML report with:
   - summary counts
   - filter buttons
   - one card per issue
   - screenshot preview
   - compact QA fields and collapsible technical details

## Command
```powershell
python "C:\Users\Jihwan Choi\.codex\skills\qv-issue-html-review\scripts\build_qv_issue_html_report.py" --input "<INPUT_XLSX>" --open
```

## Output
- Default HTML path: `<input_stem>_review.html` next to the Excel file
- Optional browser open: `--open`

## Review Focus
- Show the issue image and the final QA judgment together.
- Keep reviewer-facing labels concise.
- Use the workbook data as the source of truth; do not invent extra context.
- Prefer fast visual scanning over dense technical detail.
- For `ANALYSIS_OD_TTC_RISK` and `ANALYSIS_OD_HEADING_CHANGE`, show previous value, current value, and delta when the workbook/context provides them.
- For Heading Change, make the heading delta easy to scan because reviewers often judge severity from the previous-vs-current heading jump.

## Notes
- If `기술컨텍스트` is available, use it for image path resolution and routing metadata.
- If images are missing, still generate the report and mark the card clearly.
- The report should remain readable on both desktop and mobile browsers.
