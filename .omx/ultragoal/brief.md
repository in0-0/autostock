Execute the approved RALPLAN PRD `.omx/plans/prd-v0-2-release-confidence-20260602T150524Z.md` with test spec `.omx/plans/test-spec-v0-2-release-confidence-20260602T150524Z.md` as acceptance criteria.

Create exactly these three durable stories:

1. Safe provider-smoke preflight and bounded smoke evidence
   - Create/use ignored `config/settings.provider-smoke.local` with broker_mock or fixture portfolio, Telegram disabled/placeholders, market_data.mode real, capped max_universe_size <= 50, cache_dir set, and financial_data.dart_api_key_env set.
   - Run the smoke-profile preflight guard from the test spec.
   - Run bounded provider smoke with `env -u AUTOSTOCK_TELEGRAM_BOT_TOKEN -u AUTOSTOCK_TELEGRAM_CHAT_ID`.
   - Capture sanitized evidence for pykrx/FDR and OpenDART, or explicit blockers if credentials/provider/network are unavailable.
   - Do not run Google Sheets live read or Telegram live send. Do not print secrets.

2. Korean release documentation update
   - Update project docs under `docs/` in Korean with sanitized evidence/blockers.
   - Clearly distinguish completed OpenDART/pykrx/FDR validation from deferred P1 Google Sheets/Telegram live smoke.
   - Do not mark v0.2 complete unless evidence supports it or blockers are explicitly documented.

3. Verification, final quality gate, and scoped commit
   - Run `python3 -m pytest`.
   - Run staged forbidden-path guard and non-printing secret-safety scan.
   - Ensure no generated `data/`, `config/*.local*`, credential JSON, token, or local settings file is committed.
   - Run final ai-slop-cleaner no-op/changed-file pass and independent code-review gate required by Ultragoal.
   - Commit only intended tracked docs/planning changes with Conventional Commit + Lore trailers.

Keep the aggregate objective stable and use `.omx/ultragoal/ledger.jsonl` as the durable audit trail.
