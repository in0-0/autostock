# Spreadsheet Portfolio Source

AutoStock can use a Google Sheet as the read-only portfolio source for the
spreadsheet analysis MVP. The service reads the sheet, parses populated holding
rows, and uses the result only as analysis input. It does not write back to the
sheet and does not place orders.

## Expected Columns

Only populated holding fields are required. Optional columns may be blank.
Rows are interpreted as one consolidated portfolio input. If the same ticker
appears on multiple rows, AutoStock aggregates the quantity and evaluation for
analysis instead of treating those rows as separate managed accounts.

Recommended headers:

```text
기준일, 증권사, 계좌명, 계좌유형, 시장, 종목코드, 종목명, 티커, 자산군, 섹터,
통화, 보유수량, 평균매수가, 현재가, 평가금액, 전체 포트폴리오 비중, 목표비중,
투자전략, 투자근거, 메모
```

The parser accepts formatted Korean-style numbers such as `72,034`,
percentages such as `11.01%`, and tickers such as `KRX:069500`.

## Local Setup

1. Copy `config/settings.spreadsheet.example.yaml` to
   `config/settings.local.yaml`.
2. Fill `portfolio_source.google_sheets.spreadsheet_id` with your sheet ID.
3. Save the Google service-account JSON to
`config/google-service-account.local.json`.
4. Share the sheet with the service-account email as viewer.
5. Run:

```bash
python3 -m src.main --settings config/settings.local.yaml
```

For local smoke tests without live Google credentials, set
`portfolio_source.google_sheets.fixture_path` to a CSV or TSV file with the
same headers. This still uses the spreadsheet parser, but bypasses the Google
client. `market_data.mode: fixture` can likewise point to a local market-data
JSON file for deterministic CLI verification.

For live market providers, keep `market_data.universe` bounded and use
`market_data.request_delay_seconds` to throttle per-ticker provider calls. Set
`market_data.cache_dir` to reuse the last successful provider response between
runs, and keep `market_data.cache_max_age_days` low enough that stale prices
cannot be mistaken for current screening data.

## Safety Rules

- Keep `config/settings.local.yaml` and Google credential files local-only.
- Use Google Sheets readonly scope only.
- Do not paste private rows, sheet IDs, account labels, or credential paths into
  issues, logs, screenshots, or pull requests.
- If market-data providers fail, the report shows the failure and does not
  silently promote incomplete candidates.
