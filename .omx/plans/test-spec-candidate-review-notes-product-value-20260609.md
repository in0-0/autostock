# Test Spec: Candidate Review Notes for Weekend Review Completion

## Metadata
- Date: 2026-06-09
- Source PRD: `.omx/plans/prd-candidate-review-notes-product-value-20260609.md`
- Source requirements: `.omx/specs/deep-interview-repo-service-completeness-audit.md`

## Test Strategy
The test strategy proves that AutoStock produces useful candidate-level review notes without changing first-pass strategy/scoring behavior, without introducing order/sizing/rebalancing language, and without leaking secrets/private candidate data through debug output.

## Acceptance-to-Test Matrix
| Acceptance criterion | Test evidence |
|---|---|
| Review notes include review reason, defer/reject reason, next check, data confidence/provenance, context | Unit tests for builder plus report rendering assertions |
| No order/sizing/rebalancing language | Report text grep/assertions in unit/fixture tests |
| Ranking algorithm unchanged | Existing score tests plus regression asserting `peg_macro_v1` score inputs unchanged |
| Explain/report persistence reproducible | CLI fixture/integration test checks structured review-note fields and source context in both report JSON and explain JSON; Markdown-only evidence does not satisfy this criterion |
| Passing/risky/no-candidate/Markdown scenarios covered | New focused tests in `tests/test_phase1.py` |
| Unsafe debug prints removed | Static grep/regression check over changed files or tests capturing stdout where practical |
| Docs align after implementation | Documentation diff review and Korean doc checks |

## Unit Tests
1. **Normal passing candidate note**
   - Given a ranked candidate with financial cutoff, technical pullback, score inputs, provider provenance.
   - Expect `review_reason`, `next_check`, `data_confidence`, and source context populated.

2. **Candidate with macro/data risk note**
   - Given risks such as `macro_caution_penalty`, stale/freshness warnings, or provider warnings.
   - Expect `defer_or_reject_reason` or data-confidence warning to be explicit.

3. **No-candidate/exclusion summary**
   - Given no ranked candidates and exclusion counts.
   - Expect report tells the user why review is blocked/deferred and what to check next.

4. **Machine taxonomy preservation**
   - Given raw reasons like `provider_failed:opendart:dart_status:013`.
   - Expect human text can explain it while raw taxonomy remains in source context/explain logs.

5. **Scoring unchanged**
   - Given existing sample candidates.
   - Expect `score_policy_version == peg_macro_v1` and score formula results remain consistent.

## Integration Tests
1. **Report rendering integration**
   - `render_markdown_report` includes structured candidate review notes under “후보 검토 메모.”
   - It does not include buy quantity, target ratio, order execution, or rebalancing instructions.

2. **Artifact persistence integration**
   - CLI fixture run writes `data/reports/report_YYYY-MM-DD.json` with structured review-note fields, not only note-bearing markdown.
   - CLI fixture run writes `data/explain_logs/explain_YYYY-MM-DD.json` with structured note source context and reproducible inputs.

3. **Telegram Markdown safety**
   - MarkdownV2 escaping still works when note text contains special characters.

## E2E / Smoke Tests
- Run `python3 -m pytest`.
- If runtime output changes, run a non-live fixture CLI smoke with a temporary settings file and generated `data/` under a temp directory.
- Do not run live Google Sheets reads or Telegram sends.

## Observability and Safety Checks
- `git diff --check`
- Secret/forbidden pattern scan over intended changes and generated test artifacts:
  - `bot_token`, `chat_id`, `spreadsheet_id`, `credentials_path`, `token_path`, API-key-shaped literals.
  - `매수 수량`, `목표 비중`, `자동 주문`, `리밸런싱`, `주문 실행`, `BUY`, `SELL` where used as instruction language.
- Confirm no `print(api_key)` or `print(candidate)` remains.
- Explicitly scan changed source/tests/docs for `print(api_key)`, `print(candidate)`, secret key names, and forbidden buy/order/rebalancing language.
- Confirm stdout from fixture tests does not include raw candidate object dumps or secret-like values.

## Known Non-Tested / Out-of-Scope Areas
- Live Google Sheets/Telegram credential smoke remains P1 and is out of this plan.
- Scheduler/runbook/retry verification remains v0.3 and is out of this plan.
- New data provider validation is out of first-pass tests unless a later approved story adds a provider.

## Consensus Refinement Changelog
- Structured report/explain note fields are mandatory; Markdown-only evidence is insufficient.
- Safety regression scan is explicit for debug prints, secret key names, and forbidden current-stage purchase/order language.
- Implementation tests must verify note generation can be exercised separately from rendering logic.
