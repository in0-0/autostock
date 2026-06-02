# PRD: v0.2 Release Confidence Evidence Bundle

## Metadata

- Created UTC: 20260602T150524Z
- Source requirements: `.omx/specs/deep-interview-next-steps-spec.md`
- Context snapshot: `.omx/context/next-steps-spec-20260602T145142Z.md`
- Planning mode: `$ralplan` consensus / RALPLAN-DR short mode
- Execution boundary: Planning artifact only; no source implementation in this mode

## Requirements Summary

AutoStock v0.2 needs a final release-confidence pass focused on selected P0 live-provider evidence, not a broad feature expansion. The pass must produce bounded OpenDART and pykrx/FDR smoke evidence plus Korean release documentation updates while preserving credential safety.

## Brownfield Evidence

- `docs/STATUS.md:31` identifies the CLI pipeline command as `python3 -m src.main --settings config/settings.yaml`.
- `docs/STATUS.md:35-36` marks price data as pykrx/FDR-backed and financial data as OpenDART-backed with live smoke pending.
- `docs/STATUS.md:47` lists `OpenDART/pykrx bounded live smoke` as the P0 open issue.
- `docs/STATUS.md:48` lists real Google Sheets/Telegram credential smoke as P1, matching the interview decision to defer them.
- `src/main.py:50-80` loads market data in configured mode, resolves universe, builds provider fallback, applies financial data, and continues into strategy/report generation.
- `src/main.py:312-332` resolves real-mode KOSPI/KOSDAQ universe through pykrx then FDR with cache wrapping when configured.
- `src/main.py:343-379` applies OpenDART financial data only in real mode and records missing-key/provider failures as warnings/exclusions.
- `src/main.py:559-577` resolves Telegram credentials from env/settings, but Telegram live send is out of scope for this pass.
- `src/collectors/market_data.py:308-326` records provider fallback telemetry and all-provider-failed warnings rather than silently falling back to sample.
- `src/collectors/market_data.py:358-389` builds real-mode provider order `pykrx`, `fdr`, `naver` and wraps cache providers when `cache_dir` is present.
- `tests/test_phase1.py:830-837` verifies real mode does not fall back to sample when real providers fail.
- `tests/test_phase1.py:1210-1243` verifies Telegram delivery status and error redaction, but live Telegram send remains excluded.
- Preflight validation on 2026-06-02 KST: `python3 -m pytest` passed with 61 tests.

## RALPLAN-DR Summary

### Principles

1. Evidence before release claim: v0.2 readiness is documented only from fresh smoke/test output or explicit blocker notes.
2. Secret safety is non-negotiable: no token, key, credential JSON, chat id, or account value may be printed, documented, or committed.
3. Bound every live call: use capped universe/config, existing local credentials only, and fail closed into documented blockers.
4. Do not expand scope: no Google Sheets live read, Telegram live send, scheduling, or strategy changes in this pass.
5. Preserve auditability: explain log/report/provider telemetry evidence should be referenced in Korean release docs.

### Decision Drivers

1. P0 closure: `docs/STATUS.md:47` still requires bounded OpenDART/pykrx live smoke.
2. Credential boundary: interview selected Safe local execute but forbids credential exposure.
3. Release documentation: the final state must distinguish completed validation from deferred P1 Google Sheets/Telegram live smoke.

### Viable Options

#### Option A — Bounded provider smoke + docs (Recommended)

- Approach: run/plan capped local real-mode smoke for OpenDART and pykrx/FDR when credentials/environment are available, then update docs with evidence/blockers.
- Pros: directly closes P0, respects interview scope, creates release-quality audit trail.
- Cons: may leave credential/network blockers if local key/provider access is unavailable.

#### Option B — Docs-only release gate clarification

- Approach: do not run network smoke; update docs to define remaining smoke commands and blocker status.
- Pros: zero live-call risk; still improves release decision clarity.
- Cons: does not satisfy the user's selected `safe_local_execute` intent when credentials are available and does not close P0 evidence.

#### Option C — Full end-to-end credential smoke

- Approach: include OpenDART, pykrx/FDR, Google Sheets, and Telegram live paths.
- Pros: strongest operational confidence.
- Cons: explicitly rejected by interview non-goals for this pass; higher secret/side-effect risk.

## ADR

### Decision

Use Option A: prepare an execution plan for a bounded provider-smoke evidence bundle plus Korean release-doc updates, with fallback to documented blockers if local credentials or network/provider access are unavailable.

### Drivers

- It is the only option that directly addresses P0 while preserving the user's explicit non-goals.
- It uses existing code paths rather than adding features.
- It produces evidence suitable for release decision and later `$ultragoal` execution checkpoints.

### Alternatives Considered

- Option B docs-only: rejected as insufficient when safe local execution is allowed.
- Option C full end-to-end smoke: rejected because Google Sheets live read and Telegram live send are out of scope.

### Why Chosen

The plan should maximize v0.2 confidence per selected evidence while minimizing scope creep, secret exposure, and live side effects.

### Consequences

- v0.2 can be marked release-confident only if provider smoke succeeds or if remaining blockers are explicit and accepted.
- P1 Google Sheets/Telegram credential smoke remains documented as deferred.
- No strategy/scoring/scheduling changes should be made under this plan.

### Follow-ups

- After consensus approval, prefer `$ultragoal` to execute the plan sequentially with checkpoints.
- Use `$team` only if parallel lanes are desired for smoke execution, docs update, and secret-safety review.
- Use `$ralph` only as an explicit fallback for persistent single-owner verification.

## In Scope

- Inspect local non-tracked config/environment availability without printing secret values.
- Define or use a dedicated smoke-safe settings profile, not a blind production/local settings file.
- Prepare and/or execute bounded OpenDART smoke using existing `financial_data.provider: opendart` path.
- Prepare and/or execute bounded pykrx/FDR smoke using existing `market_data.mode: real`, `universe_provider.max_universe_size`, cache, and fallback paths.
- Capture command, date, capped settings shape, high-level result, provider warnings, exclusion counts, and generated artifact paths.
- Update Korean release/status/QA docs with evidence or blockers.
- Run `python3 -m pytest` after any execution/doc plan completion branch that modifies tracked files.
- Secret scan tracked artifacts before commit.

## Out of Scope

- Real Google Sheets credential read.
- Telegram live send.
- launchd/cron/scheduling work.
- Strategy/scoring/filter behavior changes.
- New dependencies or provider replacement.
- Asking the user to paste secrets or committing local credential/config files.

## Acceptance Criteria

1. A bounded smoke procedure exists and references concrete settings fields: `market_data.mode`, `market_data.universe_provider.max_universe_size`, `financial_data.dart_api_key_env`, and `market_data.cache_dir`.
2. OpenDART smoke is attempted only if `AUTOSTOCK_DART_API_KEY` or equivalent non-tracked local setting exists; otherwise the missing credential is documented as a blocker without printing values.
3. Smoke settings are proven safe before execution: no Google Sheets live read path and no Telegram live send path are enabled.
4. pykrx/FDR smoke is attempted with capped universe size; output documents provider success/failure, fallback telemetry, cache/stale warnings, and generated artifact paths.
5. Release docs in `docs/` are updated in Korean to show completed evidence vs deferred Google Sheets/Telegram smoke.
6. `python3 -m pytest` passes after tracked changes or failure is recorded as a release blocker.
7. Secret-safety verification runs against staged/tracked diffs; untriaged matches are blockers.
8. `git diff --cached --name-only` verifies no `data/`, `config/*.local*`, `config/*credential*`, or credential JSON files are staged.

## Implementation / Execution Plan

1. **Preflight and safety boundary**
   - Confirm git status and identify tracked/untracked local config without reading secret values.
   - Check presence, not content, of `AUTOSTOCK_DART_API_KEY` and relevant local settings files.
   - Fail closed if the selected smoke settings would perform Google Sheets live read or Telegram live send.
   - Evidence target: sanitized preflight note.

2. **Create a dedicated smoke-safe settings path if needed**
   - Use or create an untracked smoke profile such as `config/settings.provider-smoke.local`; this path is covered by the existing `*.local` ignore pattern, and execution must still verify it remains untracked/unstaged. Do not use `config/settings.local.yaml` blindly.
   - Required profile shape: `portfolio_source.type: broker_mock` or fixture-backed read-only portfolio, `telegram.bot_token`/`telegram.chat_id` empty or placeholders, Telegram env vars unset for the smoke command, `market_data.mode: real`, `market_data.universe_provider.max_universe_size` capped, cache enabled, and OpenDART key supplied only by env/local setting without printing values.
   - Executable preflight blocker: run the test-spec smoke-profile guard before smoke execution. It must load the smoke profile and print only sanitized booleans/field names; if `portfolio_source.type: google_sheets` without fixture path, non-placeholder Telegram YAML credentials, Telegram live-send environment variables, non-real market mode, uncapped universe, missing cache dir, or missing `financial_data.dart_api_key_env` are detected, stop and document the settings as unsafe for this pass. Placeholders in YAML alone are not sufficient because `src/main.py` resolves Telegram env vars first.
   - Do not add this local settings file to git.

3. **Run pykrx/FDR bounded smoke**
   - Execute `python3 -m src.main --settings <safe-local-settings>` with real mode and capped universe.
   - Capture sanitized command/result, `market_data_provider`, `market_data_warnings`, `universe_snapshot`, and generated explain/report paths.
   - If provider/network fails, record fallback telemetry and blocker.

4. **Run OpenDART bounded smoke**
   - Use same capped real-mode run or a focused run that exercises `_apply_financial_data` through the CLI.
   - Confirm financial exclusions/provenance/warnings appear in explain log.
   - If key missing, record `dart_api_key_missing` as blocker rather than requesting a key.

5. **Regression and secret verification**
   - Run `python3 -m pytest`.
   - Grep tracked changes/docs for sensitive patterns and ensure local config/data outputs are untracked/ignored.

6. **Korean release documentation update**
   - Update `docs/STATUS.md` and/or a QA guide under `docs/guides/` or `docs/qa/` with date, commands, capped scope, results, blockers, and deferred P1 smoke.
   - Keep `docs/ROADMAP.md` consistent only if release gate status changes.
   - Do not mark v0.2 complete unless smoke evidence supports it or blocker wording is explicit.

7. **Commit scoped tracked changes**
   - Stage only planning/docs artifacts and intended release-doc updates.
   - Use Conventional Commit + Lore trailers per repo policy.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Secrets appear in output/docs | Only record env var names and file paths; never values. Run secret-pattern grep before commit. |
| Provider/network instability blocks smoke | Document provider failure telemetry/blocker; do not silently replace with sample mode. |
| Capped universe is too small to prove coverage | Record cap size and treat evidence as bounded smoke, not full coverage certification. |
| Local config accidentally committed | Keep `*.local`, `config/*.local*`, and credential JSON files untracked; inspect staged files before commit. |
| Scope expands into P1/P3 work | Preserve interview non-goals and defer Google Sheets/Telegram/scheduling/strategy changes. |

## Verification Steps

- `python3 -m pytest`
- `git diff --cached --name-only` before commit; fail if staged files include `data/`, `config/*.local*`, `config/*credential*`, or credential JSON.
- `grep -RInE` secret-pattern check on staged/tracked diffs; fail on untriaged credential-like values.
- Inspect generated explain/report JSON for provider, warnings, exclusion counts, and Telegram `disabled` status without committing generated outputs

## Available Agent Types Roster

- `explore`: repo/file/symbol lookup and current implementation mapping.
- `executor`: bounded local smoke execution/docs implementation after plan approval.
- `test-engineer`: verification matrix, pytest, smoke evidence adequacy.
- `verifier`: final evidence and secret-safety claim validation.
- `writer`: Korean release documentation updates.
- `architect`: architecture/safety review of provider-smoke plan.
- `critic`: consensus quality gate and risk challenge.
- `git-master`: commit hygiene if history management is needed.

## Follow-up Staffing Guidance

### `$ultragoal` default

- Goal 1 (`executor`, medium): perform safe-local preflight and bounded pykrx/FDR/OpenDART smoke or document blockers.
- Goal 2 (`writer`, high): update Korean release/QA docs from sanitized evidence.
- Goal 3 (`verifier`, high): run pytest, staged diff review, secret-pattern check, and final evidence summary.

### `$team` option

Use Team if parallel speed is needed:

- Lane A `executor`: smoke execution and artifact extraction.
- Lane B `writer`: docs update draft from planned evidence schema.
- Lane C `verifier`/`test-engineer`: QA, secret scan, and acceptance criteria validation.

Concrete launch shape: 3 lanes / 3 workers, with a leader-owned checkpoint. Suggested launch hint: `$team .omx/plans/prd-v0-2-release-confidence-20260602T150524Z.md` and assign Lane A (`executor`) smoke-safe profile + provider smoke evidence, Lane B (`writer`) Korean release docs, Lane C (`verifier` or `test-engineer`) pytest/staged-file/secret-safety verification. Team must not run Google Sheets live read or Telegram send; any lane that detects those settings reports a blocker.

### `$ralph` explicit fallback

Use only if the user explicitly wants a single persistent owner to run smoke, fix blockers, update docs, and verify until completion.

## Team Verification Path

If executed via `$team`, Team must prove before shutdown:

1. Smoke lane returns sanitized evidence or blocker notes.
2. Docs lane updates Korean release documentation from that evidence.
3. Verification lane confirms pytest, secret scan, staged-file scope, and no committed local/generated files.
4. Leader checkpoints all three evidence groups into `$ultragoal` or the final handoff report.

## Goal-Mode Follow-up Suggestions

- `$ultragoal .omx/plans/prd-v0-2-release-confidence-20260602T150524Z.md` — recommended default durable execution path.
- `$team .omx/plans/prd-v0-2-release-confidence-20260602T150524Z.md` — use when coordinated parallel execution is desired.
- `$ralph .omx/plans/prd-v0-2-release-confidence-20260602T150524Z.md` — explicit fallback only.


## Consensus Iteration 1 Revisions

Critic required a safer settings boundary. This revision forbids blind `config/settings.local.yaml` use, defines a dedicated smoke-safe profile, adds executable non-goal guards for Google Sheets/Telegram, tightens staged-file/secret verification, and gives `$team` a concrete 3-lane shape.


## Consensus Iteration 3 Revisions

- Smoke profile path changed to `config/settings.provider-smoke.local` so the existing `*.local` ignore pattern applies.
- Test spec now requires an executable sanitized preflight guard for smoke settings.
- Secret scans must be non-printing fail-close checks (`grep -qE` or equivalent) so matched content is not echoed.


## Consensus Iteration 4 Revisions

- Smoke execution must unset `AUTOSTOCK_TELEGRAM_BOT_TOKEN` and `AUTOSTOCK_TELEGRAM_CHAT_ID`.
- Smoke-profile preflight must fail if Telegram live-send env vars are present; YAML placeholders alone are insufficient because runtime resolves env first.
