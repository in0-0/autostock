# Spreadsheet MVP Review Instructions

## Review Target

Review commit `5db2664` (`feat: enable spreadsheet portfolio analysis MVP`) on
branch `main`.

This change introduces a read-only Google Sheets portfolio source and a
spreadsheet-driven candidate analysis path. The MVP should generate buy
candidates with rationale, risks, and data provenance only. It must not place
orders, write back to the sheet, perform automatic rebalancing, or depend on a
broker account holding positions.

## Product Constraints

- Google Sheets is the user-maintained portfolio source of truth.
- Google Sheets access must be read-only.
- Broker APIs are not required for the spreadsheet MVP.
- Reports must avoid automated order, share-count sizing, and rebalancing
  language.
- Market-data failures, missing macro data, stale provider data, and incomplete
  fundamentals must be visible and conservative.
- Private spreadsheet data, sheet IDs, account IDs, credential paths, tokens,
  and secret-like values must not leak into tracked config, warnings, reports,
  or explain logs.

## Primary Files To Review

- `src/collectors/portfolio_source.py`
- `src/collectors/google_sheets.py`
- `src/collectors/market_data.py`
- `src/main.py`
- `src/models.py`
- `src/reporting.py`
- `src/collectors/broker_collector.py`
- `tests/test_phase1.py`
- `config/settings.yaml`
- `config/settings.spreadsheet.example.yaml`
- `docs/guides/SECURITY.md`
- `docs/guides/SPREADSHEET_PORTFOLIO.md`
- `docs/ROADMAP.md`

## Review Checklist

1. Source boundary
   - Confirm Google Sheets is modeled as a `PortfolioSource`, not as a broker
     connector.
   - Confirm `broker_mock` remains available for legacy sample runs.
   - Confirm unsupported `portfolio_source.type` values fail explicitly.

2. Google Sheets safety
   - Confirm the live client uses `spreadsheets().values().get(...)`.
   - Confirm the OAuth scope is
     `https://www.googleapis.com/auth/spreadsheets.readonly`.
   - Confirm fixture parsing does not require live credentials.

3. Spreadsheet parser
   - Confirm Korean rich headers and formatted numbers parse deterministically.
   - Confirm optional blank columns do not fail ingestion.
   - Confirm invalid numeric cells emit stable row warning codes without raw
     cell values.
   - Confirm duplicate tickers are treated as one consolidated portfolio input,
     as documented.

4. Market data behavior
   - Confirm `sample`, `fixture`, and `real` modes are explicit.
   - Confirm unsupported `market_data.mode` values fail explicitly.
   - Confirm real mode does not silently fall back to sample data.
   - Confirm missing macro data and all-provider failures are reported.
   - Confirm `macro_data_unavailable` and valid `RISK_OFF` macro states block
     candidate output.
   - Confirm cache payloads without macro provenance are ignored.

5. Candidate/report behavior
   - Confirm candidates include rationale, risks, and provider provenance.
   - Confirm `trade_guides` stay inactive in the MVP report path.
   - Confirm report text does not imply orders, share sizing, or rebalancing.

6. Privacy and security
   - Confirm provider exception messages are sanitized before telemetry,
     warnings, reports, or explain logs.
   - Confirm short keyed secrets, relative credential paths, spreadsheet IDs,
     and account IDs are redacted.
   - Confirm tracked config uses empty placeholders only.
   - Confirm runtime outputs and credential files are ignored.

7. Tests and docs
   - Confirm regression coverage exists for parser, provider fallback, cache
     freshness, macro gating, report language, and CLI fixture runs.
   - Confirm setup/security docs match the implemented behavior.
   - Confirm roadmap wording does not overstate the Naver fallback, which is an
     explicit last-resort stub pending parser implementation.

## Suggested Verification Commands

```bash
python3 -m pytest
PYTHONPYCACHEPREFIX=/private/tmp/autostock_pycache python3 -m py_compile src/collectors/portfolio_source.py src/collectors/google_sheets.py src/collectors/market_data.py src/main.py src/models.py src/reporting.py src/collectors/broker_collector.py
python3 -m src.main --settings config/settings.yaml
rg --glob '!docs/guides/SECURITY.md' -n "bot_token: \"[0-9]+:|chat_id: \"[0-9]+\"|spreadsheet_id: \"[A-Za-z0-9_-]{20,}|credentials_path: \"[^\"]+\"|token_path: \"[^\"]+\"|AUTOSTOCK_GOOGLE_SPREADSHEET_ID=.*[A-Za-z0-9_-]{20,}" config docs tests src
```

`rg` returning exit code `1` with no output is expected for the secret scan.

## Known Non-Goals

- Live Google Sheets credentials are not included or tested in the repository.
- Live pykrx/FDR/Naver network calls are not required for deterministic tests.
- Naver parsing is not complete; it is intentionally represented as a
  last-resort stub.
- Multi-account aggregation is not a product feature. The spreadsheet is
  treated as one consolidated portfolio input.
- Automated orders, share-count sizing, tax/fee optimization, and automatic
  rebalancing are outside this MVP.

## Expected Review Output

Please report findings first, ordered by severity, with file and line
references. Prioritize behavioral regressions, privacy leaks, source-boundary
violations, incomplete conservative gating, and missing tests. If there are no
blocking issues, explicitly state `APPROVE`.
