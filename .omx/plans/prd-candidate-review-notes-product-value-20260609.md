# PRD: Candidate Review Notes for Weekend Review Completion

## Metadata
- Date: 2026-06-09
- Mode: `$ralplan` / `$plan --consensus`
- RALPLAN-DR mode: deliberate, because the plan includes credential/private-data leak prevention.
- Source requirements: `.omx/specs/deep-interview-repo-service-completeness-audit.md`
- Context snapshot: `.omx/context/repo-service-completeness-audit-20260609T141422Z.md`
- Planning boundary: no implementation in Ralplan; execution should hand off to `$ultragoal` by default.

## Requirements Summary
AutoStock should evolve from “ranked candidate list” toward a finishable weekend review workflow by adding a candidate-level review-note concept. Each candidate note should help the user decide why to review a candidate, why to defer/reject it, what to check next, and how much confidence to place in the data.

The first implementation pass must preserve the current safe product boundary: Google Sheets read-only input, Telegram/JSON outputs, no automatic orders, no buy sizing, no target weights, no auto rebalancing, and no live broker integration. Current dirty debug prints that could expose secrets or private candidate data must be removed or treated as preflight blockers before any execution.

## Brownfield Evidence
- `docs/STATUS.md:9-15` defines the current service as Google Sheets weekend candidate review and excludes automatic orders, buy sizing, target weights, auto rebalancing, and live broker API integration.
- `docs/ROADMAP.md:10-15` frames candidates as review targets with score/rank, rationale, risk, and data source, not order instructions.
- `docs/architecture/Architecture.md:14-20` records the same product boundary, and `docs/architecture/Architecture.md:49-50` identifies `PortfolioEngine` and `src/reporting.py` as ranking/reporting touchpoints.
- `src/models.py:133-146` defines `Candidate` with `rationale`, `risks`, `review_score`, `score_inputs`, and `data_provenance`; these are sufficient inputs for a first-pass review-note schema without changing scoring.
- `src/main.py:124-141` builds candidate rationale/risks/provenance, while `src/main.py:173-233` carries exclusion/reason/provenance detail into explain logs.
- `src/main.py:242-290` renders reports and writes explain/report JSON artifacts, making this the right integration surface for persisted notes.
- `src/reporting.py:33-45` renders the current candidate list with PEG/score/tag/rationale/risk/provider, and `src/reporting.py:69-75` has a “candidate review memo” section that is currently shallow.
- Current dirty worktree evidence: `src/main.py:351` has `print(api_key)` and `src/reporting.py:37` has `print(candidate)`. These must not survive execution.
- `README.md:36-38` still presents broker connector implementation and launchd scheduling as next steps, conflicting with current product docs.

## RALPLAN-DR Summary

### Principles
1. **Review-note value over scoring churn**: improve how the user completes review without changing the core scoring algorithm in the first pass.
2. **Safety before usefulness**: no candidate review feature is acceptable if it can leak API keys, account-like data, private portfolio rows, or candidate details through debug logs.
3. **Explain-log reproducibility**: user-facing notes must be traceable to machine-readable `Candidate`, filter, risk, provenance, score-input, exclusion, and macro data.
4. **Current product boundary stays intact**: no order execution, sizing, target weights, rebalancing, live credential smoke, or scheduling/runbook work in this pass.
5. **Smallest useful data surface first**: use existing data before adding providers; allow new data only when a concrete review-note field cannot be supported otherwise.

### Decision Drivers
1. **Weekend routine completion**: user can finish candidate-by-candidate review from generated output.
2. **Trust and privacy**: no secrets/private data leak and no unsafe debug output.
3. **Testable, incremental delivery**: changes fit current CLI/report/explain architecture and can be proven with fixtures.

### Viable Options

#### Option A — Existing-data review-note layer (recommended)
Build a review-note schema from current `Candidate`, filters, score inputs, provenance, risks, macro context, and exclusion reasons. Render it in Markdown and persist it in report/explain JSON.

Pros:
- Fits current architecture and non-goals.
- Avoids dependency/provider approval risk.
- Directly improves the “candidate-by-candidate review notes” success criterion.
- Easy to test with existing fixtures and unit tests.

Cons:
- May not fully answer richer investment questions such as news, valuation history, or event risk.
- Needs careful mapping from machine labels to human-readable Korean notes.

#### Option B — Existing-data layer plus planned data-source extension hooks
Implement Option A, and add explicit backlog/design notes for future extra data fields where the current model cannot produce a meaningful next-check prompt.

Pros:
- Keeps first pass safe while acknowledging the user allowed new data sources if materially useful.
- Avoids speculative provider work until review-note gaps are visible.

Cons:
- Still does not implement new data sources immediately.
- Requires discipline to avoid vague “future provider” placeholders.

#### Option C — Add new data provider now
Introduce a new provider for candidate review notes, such as news/events or valuation-history context.

Pros:
- Could make review notes richer.
- Might directly improve “what to check next.”

Cons:
- Adds dependency/API/secret/freshness risk.
- Violates “smallest useful data surface first” unless a concrete missing field is proven.
- More likely to blur first-pass scope and delay value.

### Chosen Direction
Use **Option A with Option B-compatible extension points**. Implement review notes from existing data first, remove unsafe debug prints, and document any truly missing data as future backlog. Do not add a new provider in the first execution story unless a planner/executor proves an existing acceptance criterion cannot be satisfied without it and obtains required dependency approval.

## Pre-mortem
1. **Leak scenario**: executor runs with local credentials while debug prints remain, exposing API keys or private candidate details in terminal/logs. Mitigation: first execution story must remove unsafe prints and add a regression/static check for forbidden debug/secret patterns before any smoke run.
2. **Scope creep scenario**: review-note work turns into scoring algorithm changes or broker/order/sizing guidance. Mitigation: acceptance criteria must explicitly scan reports for no order/sizing/rebalancing language and preserve `score_policy_version` behavior.
3. **Vague-note scenario**: report adds generic prose but does not make review finishable. Mitigation: note schema must include review reason, defer/reject reason, next check, data confidence/provenance, and generation context; tests must assert all fields are present for representative scenarios.

## Proposed Architecture

### Data model
Add a small review-note structure without changing core strategy scoring. Candidate model extension options:
- Add `review_note: dict[str, Any]` or a typed dataclass/model field to `Candidate`.
- Preferred execution design: typed structure if consistent with existing dataclass style, with model_dump support inherited from `Serializable`.

Candidate review note should include:
- `review_reason`: human-readable Korean reason derived from financial/technical checks and score inputs.
- `defer_or_reject_reason`: candidate-level risks or why it should be postponed; empty/low-severity when no deferral exists.
- `next_check`: concrete user follow-up such as “check data freshness,” “review OpenDART coverage gap,” “confirm Monday gap-up risk,” or “inspect technical pullback durability.”
- `data_confidence`: concise indicator based on provider, source risk, freshness warnings, provenance, and macro/data warnings.
- `source_context`: machine-readable provenance keys so the note remains reproducible.
- `excluded_or_near_miss_context`: first-pass implementation must explicitly choose either top exclusion categories only or selected near-miss ticker notes; do not silently mix both.

### Service flow
1. Safety preflight: remove/forbid unsafe debug prints in dirty worktree areas (`src/main.py`, `src/reporting.py`).
2. Build review-note generation in a small helper/builder near candidate construction after `Candidate` is formed and before ranking/report rendering; keep this logic out of `src/reporting.py`.
3. Preserve ranking behavior in `PortfolioEngine`; do not change score formula.
4. Render review notes in `src/reporting.py` under the existing “후보 검토 메모” section, replacing the shallow one-line memo.
5. Persist structured review-note fields into report JSON and explain items; do not rely on Markdown-only evidence.
6. Align README/docs after behavior is implemented: current next steps should not direct contributors toward broker/order/rebalancing as the near-term product path.

### File-level implementation plan
1. `src/main.py`
   - Remove unsafe `print(api_key)` from current dirty change before any run.
   - Add or call review-note builder using existing candidate/filter/risk/provenance data.
   - Ensure explain items include note fields or note source fields.
2. `src/reporting.py`
   - Remove unsafe `print(candidate)` from current dirty change.
   - Render structured candidate review notes in Korean.
   - Preserve Telegram MarkdownV2 escaping through existing `render_telegram_markdown_v2` path.
3. `src/models.py`
   - Add review-note data structure if needed, preserving dataclass/Serializable style.
4. `tests/test_phase1.py`
   - Add unit/fixture tests for note generation and rendering.
   - Add regression checks that no order/sizing/rebalancing language appears in new report notes.
   - Add safety regression for no debug print/secret-like output where practical.
5. `README.md` and possibly `docs/STATUS.md` / `docs/ROADMAP.md`
   - Update Korean project-facing documentation only after behavior exists or when documenting the approved plan.
   - Align README next steps with candidate-review-note product path.

## Acceptance Criteria
1. Generated candidate output includes candidate-level review notes with: review reason, defer/reject reason, next check, data confidence/provenance, and generated context.
2. Reports remain free of automatic order, buy sizing, target-weight, and rebalancing instructions.
3. `review_score`, `score_policy_version`, and core ranking algorithm semantics remain unchanged in first-pass tests.
4. Explain logs and report JSON persist structured review-note fields plus enough machine-readable context to reproduce each note; Markdown-only evidence is insufficient.
5. Candidate note rendering is tested for at least: passing candidate, candidate with macro/data risk, no-candidate/exclusion summary, and Markdown escaping/safety.
6. Dirty debug prints capable of leaking `api_key` or candidate/private data are removed before smoke or execution.
7. Documentation updated in Korean after implementation to reflect candidate-review-note workflow and remove stale broker/rebalancing next-step emphasis.

## Implementation Steps
1. **Safety gate**: clean unsafe debug prints and add a targeted regression/static assertion for `print(api_key)`, `print(candidate)`, secret key names, and forbidden buy/order/rebalancing language.
2. **Review-note schema**: define minimal typed or serializable structure using existing project dataclass patterns.
3. **Note builder**: map current filters, rationale, risks, score inputs, data provenance, macro context, and exclusion reasons into Korean review-note fields in a helper outside rendering logic.
4. **Report integration**: replace shallow memo section with structured per-candidate notes and no-candidate/exclusion guidance.
5. **Persistence integration**: include notes in report payload and/or explain log items without breaking existing consumers.
6. **Tests**: add focused unit tests and fixture smoke coverage, then run `python3 -m pytest`.
7. **Docs**: update README and relevant Korean docs to align with the current product boundary and new review-note capability.

## Risks and Mitigations
- **Risk: note text becomes hardcoded or misleading.** Mitigation: derive note text from explicit machine fields; keep raw taxonomy in explain logs.
- **Risk: review notes imply buy advice.** Mitigation: use “검토/보류/확인” language only; test for forbidden order/sizing terms.
- **Risk: provider gaps make notes noisy.** Mitigation: data-confidence field should surface provider/freshness risk, not hide it.
- **Risk: new data source overreach.** Mitigation: start with existing data; require explicit dependency approval for new packages/providers.
- **Risk: uncommitted user changes conflict.** Mitigation: preserve unrelated files; inspect dirty diffs before editing; stage only task files.

## Expanded Test Plan
### Unit
- Review-note builder returns all required fields for normal candidate, risk candidate, and stale/provider-warning candidate.
- Korean note text maps known taxonomy labels to user-readable explanations without losing raw machine fields.
- Ranking score behavior remains unchanged.

### Integration
- CLI fixture run writes report/explain artifacts containing review notes.
- Telegram Markdown rendering still escapes special characters.
- No-candidate run shows useful exclusion/review guidance.

### E2E / smoke
- Run `python3 -m pytest`.
- Run a fixture-based CLI smoke with no live credentials if implementation changes runtime output.
- Do not run live Google Sheets or Telegram sends in this plan.

### Observability / safety
- Scan intended diffs and generated artifacts for secret patterns and forbidden current-stage language.
- Confirm no `print(api_key)` or raw candidate object debug print remains.
- Confirm report payload preserves `telegram_delivery_status` and explain log audit fields.

## Verification Steps
- `python3 -m pytest`
- `git diff --check`
- Targeted grep over changed files and generated fixture artifacts for forbidden language: `매수 수량|목표 비중|자동 주문|리밸런싱|주문 실행|bot_token|chat_id|spreadsheet_id|credentials_path|token_path`
- Optional fixture CLI smoke using non-live settings only.

## ADR
### Decision
Build candidate review notes from existing AutoStock data first, with safety cleanup as the first execution gate and new data sources deferred unless proven necessary.

### Drivers
- Weekend review completion is the user-selected product-value goal.
- Existing models already contain rationale, risks, score inputs, provenance, macro context, and exclusions.
- Secret/private data safety is a prerequisite for trust.

### Alternatives considered
- **Existing-data only, no extension hooks**: safest, but may hide legitimate future data gaps.
- **New provider now**: potentially richer, but adds dependency/API/freshness risk before the minimum useful workflow is validated.
- **Operations-first plan**: useful for v0.3 but does not satisfy the selected product-value lens.

### Why chosen
The chosen direction delivers the user-selected outcome fastest while respecting non-goals and minimizing provider/dependency risk.

### Consequences
- First pass improves report/explain usefulness more than investment strategy quality.
- Some richer context may remain backlog until review-note gaps are measured.
- Documentation should be updated to steer contributors away from stale broker/rebalancing priorities.

### Follow-ups
- Evaluate whether notes need event/news/valuation-history data after the existing-data version is used.
- Later v0.3 operations work should address scheduling, retries, and runbook separately.
- P1 live credential smoke remains separate from this product-value plan.

## Available Agent Types Roster
- `executor`: implementation/refactor in source files.
- `test-engineer`: focused tests, fixture smoke, regression coverage.
- `code-reviewer`: final code review and secret/privacy safety review.
- `architect`: design review for data model/report boundary.
- `critic`: plan/quality gate review.
- `writer`: Korean docs updates after behavior is implemented.
- `verifier`: final evidence and acceptance proof.
- `dependency-expert`: only if a new provider/package becomes necessary.

## Follow-up Staffing Guidance
### Default `$ultragoal`
Use `$ultragoal` as the durable goal ledger. Suggested stories:
1. Safety cleanup and regression guard (`executor`, medium reasoning; `test-engineer`, medium).
2. Review-note schema/builder (`executor`, medium; `architect` advisory if model boundary is unclear).
3. Report/explain integration (`executor`, medium; `test-engineer`, medium).
4. Korean documentation alignment (`writer`, high; `code-reviewer`, high).
5. Final verification/secret scan (`verifier`, high; `code-reviewer`, high).

### `$team` option
Use `$team` only if parallel delivery is desired after Ultragoal creates story boundaries:
- Lane A: schema/builder implementation.
- Lane B: report/explain rendering tests.
- Lane C: docs alignment and forbidden-language checks.
Team must return checkpoint-ready evidence to the Ultragoal ledger.

### `$ralph` fallback
Use `$ralph` only if the user explicitly wants one persistent owner to iterate until completion. It is not the recommended default because `$ultragoal` provides better durable goal tracking.

## Team Launch Hints
- `$team .omx/plans/prd-candidate-review-notes-product-value-20260609.md`
- Or under Ultragoal: create goals first, then launch Team for implementation stories that have disjoint write scopes.

## Team Verification Path
Before Team shutdown:
- all changed code/tests/docs listed by lane,
- `python3 -m pytest` evidence collected,
- no live credential actions performed,
- forbidden language/secret scans pass,
- notes are present in report/explain artifacts from fixture evidence.

## Goal-Mode Follow-up Suggestions
- Recommended: `$ultragoal create-goals --brief-file .omx/plans/prd-candidate-review-notes-product-value-20260609.md`
- Use `$team` alongside Ultragoal for parallel implementation lanes.
- `$autoresearch-goal` is not the right default; this is implementation planning, not a research deliverable.
- `$performance-goal` is not the right default; this plan is not a measurable performance optimization.

## Consensus Refinement Changelog
- Applied Architect/Critic recommendation to prefer structured note persistence in report JSON and explain logs over Markdown-only evidence.
- Made safety regression explicit for `print(api_key)`, `print(candidate)`, secret key names, and forbidden buy/order/rebalancing language.
- Clarified that review-note generation belongs in a helper/builder, not rendering logic.
- Added an explicit implementation decision point for top exclusion categories vs selected near-miss ticker notes.
