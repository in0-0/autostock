# Test Spec: v0.2 Release Confidence Evidence Bundle

## Metadata

- Created UTC: 20260602T150524Z
- PRD: `.omx/plans/prd-v0-2-release-confidence-20260602T150524Z.md`
- Source requirements: `.omx/specs/deep-interview-next-steps-spec.md`
- Context snapshot: `.omx/context/next-steps-spec-20260602T145142Z.md`

## Test Strategy

This is a release-confidence verification plan, not a feature test expansion. It proves that selected live-provider paths can run in a bounded, secret-safe way or that blockers are explicit enough for release decision-making.

## Acceptance Criteria Mapping

| PRD AC | Verification |
|---|---|
| AC1 bounded procedure | Review smoke command/settings summary includes real mode, capped `max_universe_size`, cache dir, and OpenDART env var name only. |
| AC2 OpenDART gated by credential availability | Check env/key presence without printing value; if absent, docs say blocker. If present, explain log includes financial provenance/exclusions/warnings. |
| AC3 smoke settings safe | Preflight proves selected smoke settings use broker_mock/fixture portfolio and Telegram disabled/placeholders; fail if Google Sheets live read or Telegram live send would run. |
| AC4 pykrx/FDR capped smoke | CLI smoke or provider run records `market_data_provider`, telemetry/warnings, universe snapshot, generated artifacts. |
| AC5 Korean release docs | Review `docs/STATUS.md`/QA docs for completed vs deferred evidence. |
| AC6 pytest | `python3 -m pytest` passes or failure is documented as blocker. |
| AC7 secret safety | grep staged/tracked diffs for sensitive patterns; untriaged matches block completion. |
| AC8 generated/local files uncommitted | `git diff --cached --name-only` shows no staged `data/`, `config/*.local*`, `config/*credential*`, or credential JSON. |

## Concrete Verification Commands

```bash
python3 -m pytest

# Fail closed if generated outputs, local settings, or credential artifacts are staged.
if git diff --cached --name-only | grep -qE '^(data/|config/.*\.local($|\.)|config/.*credential|config/.*token|.*credential.*\.json$)'; then
  echo "BLOCKER: generated outputs, local settings, or credential artifacts are staged"
  exit 1
fi

# Scan the actual staged diff surface without printing matched content.
if git diff --cached --unified=0 | grep -qE '(api[_-]?key|bot[_-]?token|chat[_-]?id|private_key|client_email|BEGIN ... PRIVATE KEY|[0-9]{15,})'; then
  echo "BLOCKER: staged diff contains secret-like content"
  exit 1
fi

# If execution edited tracked files before staging, scan the unstaged tracked diff without printing matched content.
if git diff --unified=0 -- docs .omx/plans .omx/specs .omx/interviews | grep -qE '(api[_-]?key|bot[_-]?token|chat[_-]?id|private_key|client_email|BEGIN ... PRIVATE KEY|[0-9]{15,})'; then
  echo "BLOCKER: unstaged tracked diff contains secret-like content"
  exit 1
fi
```

## Smoke-Profile Preflight Guard

Run this before any provider smoke command. It prints only sanitized field names / booleans and exits nonzero on non-goal violations.

```bash
python3 - <<'PY'
from pathlib import Path
import sys, yaml

settings_path = Path("config/settings.provider-smoke.local")
if not settings_path.exists():
    print("BLOCKER: smoke settings file missing: config/settings.provider-smoke.local")
    sys.exit(1)

settings = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
portfolio = settings.get("portfolio_source", {})
portfolio_type = str(portfolio.get("type", ""))
gs = portfolio.get("google_sheets", {}) or {}
telegram = settings.get("telegram", {}) or {}
market = settings.get("market_data", {}) or {}
universe_provider = market.get("universe_provider", {}) or {}
financial = settings.get("financial_data", {}) or {}

placeholder_values = {"", "REPLACE_WITH_LOCAL_TELEGRAM_BOT_TOKEN", "REPLACE_WITH_LOCAL_TELEGRAM_CHAT_ID"}
import os
telegram_yaml_safe = str(telegram.get("bot_token", "")) in placeholder_values and str(telegram.get("chat_id", "")) in placeholder_values
telegram_env_absent = not os.getenv("AUTOSTOCK_TELEGRAM_BOT_TOKEN") and not os.getenv("AUTOSTOCK_TELEGRAM_CHAT_ID")
telegram_safe = telegram_yaml_safe and telegram_env_absent
gs_live = portfolio_type == "google_sheets" and not str(gs.get("fixture_path", ""))
max_universe_size = universe_provider.get("max_universe_size")

checks = {
    "portfolio_source_not_live_google_sheets": not gs_live,
    "telegram_yaml_disabled_or_placeholder": telegram_yaml_safe,
    "telegram_env_vars_absent": telegram_env_absent,
    "market_data_mode_real": str(market.get("mode", "")) == "real",
    "max_universe_size_capped": isinstance(max_universe_size, int) and 0 < max_universe_size <= 50,
    "market_cache_dir_present": bool(market.get("cache_dir")),
    "dart_api_key_env_present": bool(financial.get("dart_api_key_env")),
}

for name, ok in checks.items():
    print(f"{name}={ok}")

if not all(checks.values()):
    print("BLOCKER: smoke settings profile is unsafe for this pass")
    sys.exit(1)
PY
```

For smoke execution after approval, use a dedicated untracked provider-smoke settings path, not the general local production settings path, for example:

```bash
env -u AUTOSTOCK_TELEGRAM_BOT_TOKEN -u AUTOSTOCK_TELEGRAM_CHAT_ID python3 -m src.main --settings config/settings.provider-smoke.local
```

Before running it, verify the profile shape without printing secret values:

```text
portfolio_source.type is broker_mock or fixture-backed, not google_sheets with live credentials
telegram.bot_token/chat_id are empty or placeholders and AUTOSTOCK_TELEGRAM_BOT_TOKEN/AUTOSTOCK_TELEGRAM_CHAT_ID are unset so delivery_status remains disabled
market_data.mode is real
market_data.universe_provider.max_universe_size is capped
market_data.cache_dir is configured
financial_data.dart_api_key_env names AUTOSTOCK_DART_API_KEY or equivalent env key, but value is never printed
```

Do not print or commit the contents of local credential files. Record only sanitized result fields.

## Evidence to Capture

- Date/time and command shape, with settings path but no secret values.
- Smoke settings safety verdict: safe / blocked, with no secret values.
- `max_universe_size` cap used.
- OpenDART credential state: `available` / `missing` / `provider_failed:<redacted>`.
- Market provider result: `pykrx`, `fdr`, `naver`, or `none` plus warnings.
- Universe snapshot count/source.
- Explain log/report filenames generated under `data/`.
- Exclusion counts and relevant provider warnings from explain log.
- `python3 -m pytest` result.
- Secret scan result.

## Negative Tests / Guardrails

- Do not run Google Sheets live credential read.
- Do not send Telegram live messages.
- Do not switch real provider failures to sample mode for release evidence.
- Do not commit generated `data/` outputs or any `config/*.local*` file.
- Do not change strategy/scoring code under this plan.

## Team Verification Path

If executed via `$team`, Team must prove before shutdown:

1. Smoke lane returns sanitized evidence or blocker notes.
2. Docs lane updates Korean release documentation from that evidence.
3. Verification lane confirms pytest, secret scan, staged-file scope, and no committed local/generated files.
4. Leader checkpoints all three evidence groups into `$ultragoal` or the final handoff report.


## Consensus Iteration 1 Revisions

- Command examples now use `config/settings.provider-smoke.local` instead of `config/settings.local.yaml`.
- Added executable non-goal guard for Google Sheets live read and Telegram live send.
- Staged-file and secret checks now have blocker semantics.


## Consensus Iteration 2 Revisions

- Secret verification now scans the actual staged diff surface with `git diff --cached --unified=0`.
- Staging hygiene now has an explicit fail-close command for `data/`, `config/*.local*`, credential/token files, and credential JSON.
- Unstaged tracked documentation/planning diffs are scanned before staging so execution can catch leaks early.


## Consensus Iteration 3 Revisions

- Smoke profile path changed to `config/settings.provider-smoke.local`, which is covered by the existing `*.local` ignore pattern.
- Added executable sanitized smoke-profile preflight guard.
- Secret scan commands now use non-printing `grep -qE` blocker checks.


## Consensus Iteration 4 Revisions

- Smoke command now unsets Telegram live-send env vars.
- Preflight guard now fails if `AUTOSTOCK_TELEGRAM_BOT_TOKEN` or `AUTOSTOCK_TELEGRAM_CHAT_ID` is present.
- Test spec explicitly states YAML placeholders alone do not disable Telegram when env vars are set.
