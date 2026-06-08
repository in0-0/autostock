Execute the deep-interview spec `.omx/specs/deep-interview-next-step-v0-2-release-closure.md` as the source of truth.

Create exactly these four durable stories:

1. OpenDART full-market validation preflight and safe run
   - Inspect existing local untracked settings/environment without printing secret values.
   - Attempt OpenDART full-market validation only when safe local credentials/settings are already available.
   - Use reasonable safeguards: cache, request delay/rate-limit awareness, bounded logs, and sanitized summaries.
   - If credentials/settings are unavailable, record a no-secret blocker/residual risk instead of asking for secrets.
   - Do not run Google Sheets live read, Telegram live send, v0.3 scheduling/runbook/retry work, broker/order/rebalancing work, release tag, or deployment.

2. Evidence interpretation and optional code/test hardening
   - Review validation output for `dart_status:013`, missing financial fields, rate-limit symptoms, API coverage gaps, or taxonomy propagation bugs.
   - Treat consistent OpenDART coverage gaps as documentable residual risk, not v0.2 blockers.
   - If a real code/taxonomy propagation bug is found, fix it only within existing provider/reporting boundaries and add or adjust tests.
   - Preserve `provider_failed:opendart:dart_status:013` and existing `missing_*` exclusion behavior; do not change scoring/strategy or add providers/dependencies.

3. Korean v0.2 release-closure documentation
   - Update Korean project docs under `docs/` to summarize sanitized full-market evidence or the safe-skip blocker.
   - Explain whether OpenDART coverage gaps such as `dart_status:013` block v0.2; the default interview decision is residual risk when code/tests/taxonomy are consistent.
   - Keep current product scope clear: Google Sheets-based weekend candidate review only, no automatic orders/buy sizing/target weights/auto-rebalancing/current broker integration.
   - Do not include API keys, credential paths/values, spreadsheet IDs, Telegram tokens/chat IDs, account identifiers, private portfolio rows, or generated runtime data.

4. Final verification, cleanup/review gate, and safe commit
   - Run `python3 -m pytest` after any code/test changes; run the smallest relevant validation for docs-only changes.
   - Run git diff checks and a non-printing secret-safety review over intended tracked changes.
   - Run the mandatory Ultragoal final cleanup/review gate before marking the aggregate goal complete.
   - Stage and commit only task-related tracked changes with Conventional Commit plus Lore trailers.
   - Do not commit generated `data/`, local settings, credential files, tokens, private portfolio data, unrelated existing changes, or release/deployment artifacts.

Keep the aggregate objective stable and use `.omx/ultragoal/ledger.jsonl` as the durable audit trail.
