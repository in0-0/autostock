# PRD: Meaningful Macro and Growth-Candidate Report

## Source
- Deep-interview spec: `.omx/specs/deep-interview-macro-growth-report-meaning.md`
- Context snapshot: `.omx/context/macro-growth-report-meaning-20260602T154915Z.md`
- Planning mode: `$ralplan` / `$plan --consensus` short mode

## Problem
AutoStock's current weekly report exposes raw unavailable data and internal diagnostics instead of helping the owner decide what to verify next. In `src/reporting.py:28-31`, macro status renders raw booleans and nullable fields (`KOSPI 10MA`, `KOSDAQ 10MA`, `us_rate`, `yield_curve_10y2y`). In `src/reporting.py:45-50`, empty candidates render a generic message plus raw exclusion keys. In `src/reporting.py:52-62`, user-relevant data gaps and operational/system statuses are mixed in one warning section.

## Goals
1. Make degraded macro/candidate states useful by explaining decision limits and next verification tasks.
2. Preserve conservative final candidate behavior from `src/engines/portfolio.py:16-21`; do not relax `min_candidates` or candidate thresholds in this pass.
3. Replace raw booleans, `None`, and internal diagnostic keys with Korean user-facing explanations.
4. Separate user-actionable data verification from lower-level system/operational noise.
5. Keep implementation small and testable within existing report/data boundaries.

## Non-goals and Decision Boundaries
The interview recorded no broad non-goals, but the following are outside autonomous first-pass authority:
- Do not change final buy-candidate thresholds, `min_candidates`, or conservative blocking policy (`src/engines/portfolio.py:16-21`).
- Do not create a separate watchlist/partial-candidate product feature.
- Do not add or replace macro/fundamental providers.
- Do not perform live credential/Telegram/Google Sheets/OpenDART operations.

Autonomous decisions allowed:
- Korean report wording and section structure.
- Diagnostic classification and user-facing explanation mapping.

## RALPLAN-DR Summary

### Principles
1. **Decision-support over raw telemetry**: the report should answer “what should I verify next?” before exposing provider internals.
2. **Conservative candidate integrity**: final buy/growth-candidate output remains conservative unless explicitly replanned.
3. **Degraded-state transparency**: unavailable macro/fundamental inputs must be visible, but translated into actionable context.
4. **Small boundary-preserving change**: prefer reporting helpers over collector/provider rewrites.
5. **Regression-backed Korean copy**: user-visible Korean text changes must be covered by tests.

### Decision Drivers
1. User outcome: a useful report even when candidates are empty or macro data is unavailable.
2. Risk control: avoid accidental investment-advice strengthening or threshold loosening.
3. Implementation fit: current issue is concentrated in `src/reporting.py:28-74` with diagnostic inputs from `src/main.py:242-264` and `src/collectors/market_data.py:392-399`.

### Viable Options

#### Option A — Reporting-layer formatter and diagnostic mapper (Recommended)
- Approach: Add helpers in/near `src/reporting.py` that format macro state, classify exclusion/warning keys, create top-3 verification tasks, and render separated user/system sections.
- Pros: Minimal scope, preserves candidate/provider policies, directly addresses acceptance criteria.
- Cons: Does not improve actual data collection quality; mapping may need future expansion.

#### Option B — Explain-log/domain object first, report consumes richer structure
- Approach: Introduce a structured diagnostic summary generated in `src/main.py` before report rendering, then render it.
- Pros: Cleaner separation if diagnostics later feed non-Telegram outputs.
- Cons: Larger surface; risks premature abstraction for one report; more tests and model changes.

#### Option C — Data-provider remediation first
- Approach: Fix pykrx/FDR macro and OpenDART coverage so report has fewer gaps.
- Pros: Improves root data quality.
- Cons: Outside decision boundary; higher operational uncertainty; does not solve raw/noisy rendering by itself.

### Recommendation
Choose Option A. It satisfies the clarified spec while preserving existing portfolio/candidate/provider boundaries.

## Requirements

### R1. Macro interpretation
- If `macro_indicators["macro_data_unavailable"]` is true, macro section must not show `KOSPI 10MA: False`, `KOSDAQ 10MA: False`, `미국 기준금리: None`, or `장단기 금리차: None` as raw values.
- Render Korean interpretation such as “거시 데이터 부족으로 추세 판단 제한” and include which indicators need verification.
- If data is available, booleans may still be translated into Korean trend labels instead of raw `True`/`False`.

### R2. Empty candidate explanation
- When `ranked_candidates` is empty, render a useful “candidate review status” that explains whether the cause is insufficient candidates, data gaps, provider failures, or macro risk-off context.
- Preserve the final candidate empty state; do not generate provisional buy candidates.

### R3. Diagnostic classification
- Centralize the report-facing taxonomy in one explicit helper/table so diagnostic wording is not scattered across ad hoc string checks. Keep it local to reporting for this pass; extract later only if another output needs the same semantics.
- Map raw reasons like `missing_peg_inputs`, `missing_roe_inputs`, `missing_net_income_growth_inputs`, `missing_debt_ratio_inputs`, and `provider_failed:opendart:dart_status:013` into Korean categories.
- Keep counts, but group/translate them so the owner can understand what data source or financial input needs attention.
- User-facing report lines must not expose raw internal/provider keys. Unknown reasons should be shown as a Korean fallback such as “기타 데이터 확인 필요” without leaking the raw key in the normal user-facing section; raw details may remain only in existing JSON/explain artifacts or a clearly non-user debug artifact.

### R4. Verification tasks
- Build at most 3 prioritized verification tasks from macro warnings, candidate exclusion counts, portfolio source warnings, and provider failures.
- Each task should include: concise Korean action, reason/impact, and source category.
- Synthesis must be deterministic: normalize raw reasons into source categories, deduplicate by category, apply the priority order below, then cap at 3 after deduplication. Ties within a category should prefer the larger count, then stable label order.
- Priority order: macro unavailable/risk-off context, provider failure, missing core valuation/growth inputs, missing ROE/debt ratio inputs, stale/short price series, portfolio row hygiene, remaining system details.


### Diagnostic taxonomy labels for implementation
Use these Korean category labels as the starting taxonomy to reduce executor wording drift:
- `macro_unavailable_or_risk_off`: 거시 판단 데이터 확인 필요
- `provider_failure`: 외부 데이터 제공자 응답 확인 필요
- `valuation_growth_inputs`: 밸류에이션/성장성 입력 확인 필요
- `profitability_safety_inputs`: 수익성/재무안정성 입력 확인 필요
- `price_series_quality`: 가격/거래량 시계열 확인 필요
- `portfolio_input_hygiene`: 포트폴리오 입력값 확인 필요
- `operational_status`: 운영 상태 확인
- `unknown_data_gap`: 기타 데이터 확인 필요

`ip_changed_flag` should be treated as user-actionable verification because it may affect account/provider access. Telegram delivery remains operational status, not verification guidance.

### R5. Warning separation
- User-actionable data checks must render in an explicit “검증 필요” section.
- Low-level warnings and statuses such as Telegram delivery must render in a lower-priority “운영 상태” or system-status section and must not appear in the “검증 필요” section.
- Low-level warnings may remain visible in the system section, but should not dominate the report.

## Acceptance Criteria
1. A report rendered with unavailable macro data contains no raw `KOSPI 10MA: False`, `KOSDAQ 10MA: False`, `미국 기준금리: None`, or `장단기 금리차: None` strings.
2. The same report includes Korean text indicating macro judgment is limited because data is unavailable.
3. Empty candidate output includes at least one useful explanation and at least one verification task when exclusion counts or provider warnings exist.
4. `missing_peg_inputs`, `missing_net_income_growth_inputs`, `missing_roe_inputs`, `missing_debt_ratio_inputs`, and `provider_failed:opendart:dart_status:013` are translated/grouped into Korean diagnostic labels in the user-facing report.
5. User-facing report lines do not expose raw diagnostic keys; raw keys may remain in JSON/explain/debug artifacts only.
6. Verification tasks are deduplicated by category, deterministically ordered, and capped at 3 items after deduplication.
7. Telegram delivery status is separated from user-actionable verification guidance.
8. Existing positive candidate rendering remains intact for `ranked_candidates`.
9. Macro `RISK_OFF` empty-candidate output explains macro blocking separately from provider/input data gaps.
10. `python3 -m pytest` passes.

## Implementation Plan
1. Add small formatting/classification helpers in `src/reporting.py` or a local reporting helper module if readability demands it.
   - Candidate helper names: `_format_macro_summary`, `_classify_candidate_exclusion`, `_build_verification_tasks`, `_split_warning_sections`.
2. Update `render_markdown_report` (`src/reporting.py:9-77`) to use interpreted macro text, translated candidate diagnostics, verification tasks, and separated system status.
3. Keep `PortfolioEngine.rank_candidates` behavior unchanged (`src/engines/portfolio.py:16-21`).
4. Add focused regression tests in `tests/test_phase1.py` or a new `tests/test_reporting.py` for unavailable macro, raw reason translation, top-3 cap, warning separation, and non-empty candidate preservation.
5. If report snapshot expectations exist, update them only for intended Korean copy changes.
6. Run `python3 -m pytest`.

## Risks and Mitigations
- Risk: Korean copy becomes too verbose for Telegram. Mitigation: cap verification tasks at 3 and keep diagnostics grouped.
- Risk: Mapping misses a future reason key. Mitigation: provide safe fallback category and test unknown-key behavior.
- Risk: Separation hides operational failures. Mitigation: keep system status visible but below actionable verification guidance.
- Risk: Tests become brittle on exact full report text. Mitigation: assert key substrings and absence of raw values rather than whole-message snapshots.

## Verification Plan
- Unit/report tests:
  - Unavailable macro does not render raw booleans/None.
  - Empty candidates + exclusion counts render Korean diagnostic categories.
  - Verification task count is <= 3.
  - Telegram status appears in a system/operational section, not the verification guidance section.
  - Existing candidate details still render rank, name, ticker, PEG, score, rationale/risks/provider.
  - `ip_changed_flag` appears as actionable verification, while Telegram delivery appears only as operational status.
  - One combined realistic degraded-report case mirrors the user-provided painful output.
- Full suite: `python3 -m pytest`.

## ADR

### Decision
Use a reporting-layer formatter and diagnostic mapper to make degraded macro/candidate output actionable without changing candidate thresholds or data providers.

### Drivers
- User wants verification guidance when data is incomplete.
- The current raw/noisy output is concentrated in `src/reporting.py`.
- Decision boundaries allow report structure and diagnostic classification, but not threshold/provider changes.

### Alternatives considered
- Structured diagnostic object in `src/main.py`: cleaner long-term but larger than needed.
- Provider/data remediation: important future work but outside current autonomous scope.
- Relax candidate criteria: rejected because final candidate conservatism must remain.

### Why chosen
Option A best satisfies the spec with the smallest reversible change and clearest tests.

### Consequences
- Report will be more useful in degraded data states.
- Actual data coverage remains unchanged and should be handled by a later provider/data-quality plan.
- Diagnostic mappings become a maintained product surface.

### Follow-ups
- Later plan for macro/fundamental provider quality if owner wants fewer degraded reports.
- Later plan for a true watchlist/partial-candidate feature if desired.

## Available Agent Types Roster
- `executor`: implement reporting helpers and tests.
- `test-engineer`: strengthen/reporting regression coverage.
- `code-reviewer`: review final diff for behavior, copy safety, and boundary compliance.
- `verifier`: validate acceptance criteria and pytest evidence.
- `writer`: update Korean docs if implementation changes report contract.
- `architect`: revisit if plan expands into diagnostic domain model/provider changes.
- `critic`: re-review if execution proposes threshold/provider/watchlist changes.

## Follow-up Staffing Guidance
- Default `$ultragoal`: one `executor` lane, then `verifier`; reasoning medium for implementation, high for verification.
- `$team` option: use only if parallelizing implementation/test/docs:
  - Lane 1 `executor`: `src/reporting.py` helpers/rendering.
  - Lane 2 `test-engineer`: reporting regression tests.
  - Lane 3 `writer` if docs/report contract updates are needed.
  - Verification lane `verifier` after integration.
- `$ralph` fallback: only if owner explicitly wants a single persistent owner to implement, test, and iterate.

## Goal-Mode Follow-up Suggestions
- Recommended: `$ultragoal .omx/plans/prd-macro-growth-report-meaning.md` for durable sequential implementation tracking.
- Parallel option: `$team .omx/plans/prd-macro-growth-report-meaning.md` with Ultragoal checkpointing if implementation/test/docs are split.
- Not recommended here: `$autoresearch-goal` (not a research deliverable) and `$performance-goal` (not an optimization task).

## Team Launch Hints
- `$team .omx/plans/prd-macro-growth-report-meaning.md`
- Or shell-native: `omx team .omx/plans/prd-macro-growth-report-meaning.md`

## Team Verification Path
Team must prove:
1. Source changes stay within report/diagnostic classification unless explicitly approved.
2. All acceptance criteria are covered by tests.
3. `python3 -m pytest` passes.
4. Final report no longer exposes raw `False`/`None`/internal keys in user-facing sections.

## Applied Consensus Improvements
- Applied Architect iteration 1 feedback: tightened raw-key user-facing rule, expanded taxonomy coverage, defined deterministic verification-task synthesis, made the `검증 필요` vs `운영 상태` section split explicit, and added macro `RISK_OFF` empty-candidate coverage to acceptance/test planning.
- Applied Critic approval improvements: added explicit taxonomy labels, classified `ip_changed_flag` as actionable verification while Telegram remains operational, and added a combined realistic degraded-report regression target.
