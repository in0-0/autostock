# Deep Interview Spec: Repo Service Completeness / Product-Value Audit

## Metadata
- Profile: standard
- Context type: brownfield
- Final ambiguity: 13%
- Threshold: 20%
- Context snapshot: `.omx/context/repo-service-completeness-audit-20260609T141422Z.md`
- Transcript: see latest `.omx/interviews/repo-service-completeness-audit-*.md`

## Intent
Improve AutoStock's product value by making the weekend candidate-review routine finishable for the user. The focus is not generic release closure or operations maturity; it is whether the output helps the user complete candidate-by-candidate review.

## Desired outcome
AutoStock should produce or support candidate-level review notes that let the user understand, for each candidate:
1. why this candidate is worth reviewing,
2. why it might be deferred/rejected,
3. what concrete follow-up check is needed next,
4. what data/provenance/risk context shaped the note.

## In scope
- Audit current repo/service gaps through the lens of product value and weekend review workflow completeness.
- Prioritize improvements that transform existing candidate output from a ranked list into usable candidate review notes.
- Use existing score/filter/provenance/risk/exclusion data when sufficient.
- If materially valuable, propose or implement new data-source support in a later execution phase, subject to project safety and dependency rules.
- Treat current dirty worktree safety issues as preflight blockers or immediate safety defects for any execution handoff.
- Recommend documentation alignment where README/status/roadmap conflict with the current product boundary.

## Out of scope / Non-goals for first pass
- Automatic orders, buy sizing, target weights, auto rebalancing, or broker order execution.
- Changing the core scoring algorithm or strategy policy as the first-pass product-value fix.
- Live Google Sheets/Telegram credential smoke or credential-gated validation.
- v0.3 operations scheduling, launchd setup, runbook, rollback procedure, or retry policy implementation.

## Decision boundaries
OMX may autonomously:
- rank product-value gaps by severity and user impact,
- design a candidate-review-note schema using existing filters, rationale, risks, provider provenance, score inputs, exclusion counts, and macro context,
- remove or require removal of unsafe debug prints before any execution that could expose secrets/private data,
- update `.omx` planning artifacts and propose Korean public-doc changes.

OMX may plan or implement new data-source support only if:
- it directly supports candidate review-note usefulness,
- it does not violate secret-handling rules,
- new package/dependency introduction receives explicit approval if required by project instructions,
- it remains outside automatic order/sizing/rebalancing behavior.

OMX must not autonomously:
- run live credentials, Google Sheets live reads, or Telegram live sends,
- deploy/schedule production jobs,
- add order execution or portfolio sizing recommendations,
- treat uncommitted user/WIP changes as disposable unless explicitly authorized.

## Product-value problem list discovered in preflight

### P0 — Unsafe current dirty debug prints can destroy trust
- Evidence: current dirty diff contains `print(api_key)` in `src/main.py` and `print(candidate)` in `src/reporting.py`.
- Product impact: any review workflow that leaks API keys or candidate/private portfolio context is not trustworthy.
- First-pass handling: require safety cleanup before execution or treat as a blocking preflight defect.

### P1 — Output is a ranked candidate list, not a complete review note
- Evidence: `src/reporting.py` lists PEG/score/tag/rationale/risks/provider; `src/main.py` carries richer filters/provenance/score inputs mostly into explain logs.
- Product impact: user still has to mentally assemble “why review / why defer / what to check next.”
- Improvement direction: candidate review-note schema and rendering.

### P1 — Candidate rationale is too machine-oriented
- Evidence: current rationale values are labels such as `financial_cutoff_passed` and strategy tags.
- Product impact: labels are audit-friendly but not enough for a weekend human review routine.
- Improvement direction: render human-readable reasons with key values and thresholds while preserving machine taxonomy in explain logs.

### P1 — Defer/reject logic is under-presented for near-miss or excluded candidates
- Evidence: exclusion counts are shown when no candidates pass; explain logs have richer per-ticker risks/exclusions.
- Product impact: user cannot easily tell whether no/low candidates means market risk, missing data, stale provider output, technical failure, or strict filters.
- Improvement direction: include structured “why not now” notes for selected excluded/near-miss cases or top exclusion categories.

### P2 — Follow-up checks are not explicit
- Evidence: report has risks and system warnings but no candidate-level “next check” field.
- Product impact: user cannot finish the routine by knowing exactly what to inspect next.
- Improvement direction: map risks/provenance/freshness/macros to candidate-level next-check prompts.

### P2 — Product docs are partially inconsistent
- Evidence: README still lists broker connectors and rebalancing guide as next implementation steps while newer docs exclude broker/order/rebalancing from current scope.
- Product impact: next contributors or users may optimize the wrong product.
- Improvement direction: align README with current Google Sheets weekend review service definition.

### P2 — Data/provider residual risk affects review confidence
- Evidence: docs record public universe provider full-load failures and OpenDART coverage gaps as residual risk.
- Product impact: candidate notes should surface data confidence, not hide provider limitations.
- Improvement direction: convert provider provenance/freshness/risk into user-facing confidence notes.

## Acceptance criteria for a follow-up plan or implementation
- Candidate output includes a structured candidate-review-note concept with at least: review reason, defer/reject risk, next check, data confidence/provenance, and timestamp/context.
- Telegram/Markdown report presents review notes without order/sizing/rebalancing language.
- Explain logs preserve machine-readable taxonomy and include enough data to reproduce review notes.
- Unsafe debug prints are absent before any run that could touch local credentials or portfolio data.
- Tests or fixture smoke prove the note rendering for: passing candidate, candidate with risk warning, no-candidate/exclusion summary, and Telegram Markdown escaping/safety.
- Public docs, if updated, are Korean and align README/STATUS/ROADMAP around the weekend candidate-review product boundary.

## Suggested handoff
Default: `$ultragoal create-goals --brief-file .omx/specs/deep-interview-repo-service-completeness-audit.md`, then complete goals sequentially.

Use `$ralplan` first if the next step should produce a consensus PRD/test spec before implementation, especially because new data-source support may expand architecture or dependency surface.
