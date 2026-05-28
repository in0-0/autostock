# Security Guide

AutoStock may handle broker credentials, Google Sheets credentials, spreadsheet
IDs, Telegram bot tokens, chat IDs, account numbers, and portfolio data. Treat
all of these as secrets.

## Rules

- Do not commit live credentials or account identifiers.
- Prefer environment variables or local-only settings files for secrets.
- Keep generated portfolio/report/explain artifacts out of source control.
- Redact tokens and account numbers from logs, screenshots, issues, and PRs.
- Redact spreadsheet IDs, credential paths, token paths, account labels, and
  private portfolio rows from logs, screenshots, issues, and PRs.
- When adding real broker connectors, isolate authentication in connector code
  and keep credential parsing explicit and typed.
- Google Sheets access must use readonly scope and local-only credential/token
  files. The service must not update, append, or batch-update user sheets in the
  MVP.

## Suggested Local Pattern

Use tracked sample configuration for safe defaults and a local override for real
credentials:

```text
config/settings.yaml
config/settings.local.yaml   # ignored, local secrets only
config/google-service-account.local.json
config/google-token.local.json
```

Google Sheets fields can also be provided through local environment variables:

```text
AUTOSTOCK_GOOGLE_SPREADSHEET_ID
AUTOSTOCK_GOOGLE_SHEETS_RANGE
AUTOSTOCK_GOOGLE_CREDENTIALS_PATH
AUTOSTOCK_GOOGLE_TOKEN_PATH
```

Before publishing, run:

```bash
git diff --cached
git status --short
python3 -m pytest
rg --glob '!docs/guides/SECURITY.md' -n "bot_token: \"[0-9]+:|chat_id: \"[0-9]+\"|spreadsheet_id: \"[A-Za-z0-9_-]{20,}|credentials_path: \"[^\"]+\"|token_path: \"[^\"]+\"" config docs tests src
```
