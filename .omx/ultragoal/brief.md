Execute the approved RALPLAN PRD `.omx/plans/prd-opendart-v0-2-p0-coverage-hardening.md` and test spec `.omx/plans/test-spec-opendart-v0-2-p0-coverage-hardening.md` as acceptance criteria.

Create exactly these three durable stories:

1. OpenDART taxonomy regression hardening
   - Add deterministic tests near the existing OpenDART tests.
   - Prove a DART response with status `013` becomes `provider_failed:opendart:dart_status:013` and does not crash.
   - Include the named `_apply_financial_data` propagation test: `test_apply_financial_data_records_dart_status_013_as_provider_failure_exclusion` or an equivalent clear name.
   - Preserve existing missing financial input behavior and tests for `missing_*` exclusions.
   - Do not reclassify `dart_status:013`, add new providers, add dependencies, or change scoring/strategy.

2. Korean release-readiness documentation update
   - Update Korean project docs under `docs/` to explain the v0.2 P0 interpretation after hardening.
   - Keep raw machine taxonomy stable; explain human interpretation in docs.
   - If live verification is skipped, say deterministic hardening is complete but full live coverage remains unverified.
   - Do not run or document Google Sheets live read, Telegram live send, broker/order/rebalancing scope, or secret values.

3. Verification, optional safe live evidence, and final quality gate
   - Run `python3 -m pytest`.
   - Run `git diff --check` and a non-printing secret-safety scan over `config docs tests src`.
   - If existing ignored local OpenDART credentials/settings are available, run optional full-market or large-universe live verification with cache/delay/rate-limit safeguards and sanitized evidence only; otherwise record a safe skip reason.
   - Run the mandatory Ultragoal final cleanup/review gate before marking the aggregate Codex goal complete.
   - Commit only intended tracked changes with Conventional Commit + Lore trailers; do not commit generated `data/`, local settings, credential files, tokens, or private portfolio data.

Keep the aggregate objective stable and use `.omx/ultragoal/ledger.jsonl` as the durable audit trail.
