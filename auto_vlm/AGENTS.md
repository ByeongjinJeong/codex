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

When running or testing a workbook, do not stop at evidence artifacts just
because review tasks are pending. Continue through the available review,
validation, and report stages; if a required stage cannot run, report the run as
incomplete instead of successful.

For any user request like "test this Excel workbook", "run VLM test", or
"workbook full pipeline", first read and follow:

```text
docs/testing/WORKBOOK_RUNBOOK.md
```

That document is the execution contract for workbook tests. It takes precedence
over smoke-test or planning docs for run procedure. In particular, do not replace
packet-by-packet VLM review with contact sheets, merged images, raw-frame sweeps,
or a directly authored aggregate `llm_review_results.json`.

## VLM Issue Fix Rule

When a missed or wrong VLM judgment is reported, do not patch only that one frame
or one issue type. First identify the failed shared contract across packet input,
feature-level evidence, review-result validation, report visibility, and tests,
then fix the smallest mechanism that prevents the same class of miss across
OD/LD/RBD/TS/TL.
