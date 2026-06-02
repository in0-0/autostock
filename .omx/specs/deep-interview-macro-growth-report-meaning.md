# Deep Interview Spec: Meaningful Macro and Growth-Candidate Report

## Metadata
- Source workflow: `$deep-interview`
- Profile: standard
- Context type: brownfield
- Final ambiguity: 13%
- Threshold: 20%
- Context snapshot: `.omx/context/macro-growth-report-meaning-20260602T154915Z.md`
- Transcript: see latest `.omx/interviews/macro-growth-report-meaning-*.md`

## Intent
Improve AutoStock's weekly Telegram/service report so it helps the user decide what to verify next when macro and candidate data are incomplete. The report should not merely expose raw provider failures or empty candidate output.

## Desired Outcome
A report that separates:
1. Final decision/candidate output, which remains conservative.
2. Diagnostic/verification guidance, which explains what data gaps matter and what the user should check next.
3. System/operational noise, which should not obscure user-facing investment-review meaning.

## In Scope
- Improve report copy and section structure in the macro/candidate/warning areas.
- Classify and translate internal diagnostic keys into user-facing explanations.
- Replace raw `False`, `None`, and internal provider keys with meaningful Korean status text.
- Provide a prioritized “verification tasks” section, capped at top 3 items, when data quality blocks useful candidate output.
- Make the “no candidates” state useful by explaining why there are no actionable candidates and what to verify next.
- Separate user-actionable warnings from low-level system/provider noise.
- Add/update tests that verify the new report behavior against unavailable macro data, raw exclusion reasons, and empty candidate output.

## Out of Scope / Non-goals
The user stated there are no explicit non-goals besides meeting the target spec. However, decision-boundary constraints below limit what can be changed autonomously in the first pass.

## Decision Boundaries
OMX/Codex may decide without further confirmation:
- Report wording and structure.
- Diagnostic classification and user-facing explanation mapping.

OMX/Codex should not autonomously decide these without a follow-up plan/approval:
- Changing final buy-candidate thresholds, `min_candidates`, or conservative candidate blocking policy.
- Creating a new watchlist/partial-candidate policy as a product feature.
- Adding or replacing macro/fundamental data providers.
- Performing credential/live operational work.

## Constraints
- Preserve conservative final candidate behavior unless a later approved plan changes it.
- Do not turn the report into stronger investment advice; keep wording centered on review, verification, and decision support.
- Keep changes small, testable, and aligned with existing module boundaries.
- Use Korean for project-facing docs/report copy.

## Testable Acceptance Criteria
1. Macro section must not render raw `False`/`None` values for unavailable indicators; it must render a Korean interpretation such as data unavailable, judgment limited, or verification needed.
2. When macro data is unavailable, the report must explain that macro judgment is limited and include a relevant verification task instead of only showing `CAUTION` and booleans.
3. Empty candidate output must include a useful explanation of why actionable candidates are absent and what to verify next.
4. Raw internal reasons such as `missing_peg_inputs`, `provider_failed:opendart:dart_status:013`, and `missing_roe_inputs` must be translated or grouped into user-facing diagnostic categories.
5. The report must include at most three prioritized verification tasks when data gaps or provider failures materially affect usefulness.
6. User-actionable data checks must be visually/structurally separated from low-level system warnings or Telegram delivery status.
7. Regression tests must cover unavailable macro data, empty candidate output, raw exclusion reason mapping, and warning separation.

## Assumptions and Resolutions
- Assumption: “Meaningful” means better recommendations. Resolution: It means better verification guidance first.
- Assumption: Empty candidate output should be fixed by relaxing filters. Resolution: Do not relax final candidate policy in this pass; improve explanation and diagnostic usefulness.
- Assumption: Provider failures should be solved directly. Resolution: Provider changes are outside autonomous first-pass authority; classify and explain current failures instead.

## Brownfield Evidence vs Inference
Evidence:
- `src/reporting.py` currently renders raw macro indicators and exclusion keys.
- `src/engines/macro.py` treats unavailable macro as `CAUTION`.
- `src/engines/portfolio.py` hides ranked candidates below `min_candidates`.
- `src/collectors/market_data.py` emits provider and macro unavailable warnings.

Inference:
- The most direct first-pass implementation surface is report rendering plus diagnostic mapping, with tests in `tests/test_phase1.py` or a focused reporting test module.

## Recommended Handoff
Recommended next workflow: `$ralplan` using this spec, because the change needs a small product/reporting plan and test-shape review before implementation.

Suggested invocation:
`$plan --consensus --direct .omx/specs/deep-interview-macro-growth-report-meaning.md`

Alternative: `$autopilot .omx/specs/deep-interview-macro-growth-report-meaning.md` if the owner wants direct plan+execute after this interview.
