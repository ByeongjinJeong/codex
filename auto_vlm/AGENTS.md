# Codex Project Instructions

Keep this file short. Add only rules that should apply to every Codex session in
this repository.

## Work Style Rule

Bias toward caution over speed. Before non-trivial code or LLM-workflow changes,
state assumptions, ambiguity, tradeoffs, and a brief plan with verification checks.
If the request has multiple plausible meanings or important missing context, ask
before implementing instead of choosing silently.

Keep changes surgical and simple. Touch only files directly needed for the
request, match existing style, avoid speculative abstractions or configurability,
and remove only unused code created by your own change. Every changed line should
trace back to the user's request.

Turn work into verifiable success criteria. For bug fixes, reproduce or encode
the failure first when feasible, then fix it and run the relevant tests or
workflow. If verification cannot be run, say exactly why.

## Auto VLM Operating Rule

When the user asks to run, rerun, test, review, or generate results for an input
workbook, follow the durable workflow in:

```text
docs/testing/AUTO_VLM_WORKBOOK_RUN_WORKFLOW.md
```

Do not replace that workflow with ad hoc output names, evidence-only stops, or
untracked assistant judgment artifacts unless the user explicitly asks for a
different mode.

## VLM Issue Fix Rule

When a missed or wrong VLM judgment is reported, do not patch only that one frame
or one issue type. First identify the failed shared contract across packet input,
feature-level evidence, review-result validation, report visibility, and tests,
then fix the smallest mechanism that prevents the same class of miss across
OD/LD/RBD/TS/TL.
