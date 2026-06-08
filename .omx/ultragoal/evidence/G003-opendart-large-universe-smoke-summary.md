# G003 50-Stock OpenDART Smoke Evidence

- Run date: 2026-06-08 KST
- Command shape: temporary sanitized YAML + `AUTOSTOCK_DART_API_KEY` env, `python3 -m src.main --settings <tempfile>`
- Secret values printed: false
- Google Sheets live read: false
- Telegram live send: false
- Telegram delivery status: `disabled`
- Market data provider: `pykrx`
- Macro status/provider: `CAUTION` / `unavailable`
- Universe snapshot (FDR/cache-backed): `{'source': 'fdr_universe', 'source_risk': 'package_public_source', 'count': 50, 'markets': ['KOSPI', 'KOSDAQ'], 'collected_at': '2026-06-02T23:46:37.457882'}`
- Exclusion counts: `{'missing_peg_inputs': 31, 'provider_failed:opendart:dart_status:013': 19, 'missing_net_income_growth_inputs': 14, 'missing_roe_inputs': 5, 'missing_debt_ratio_inputs': 2, 'missing_revenue': 1}`
- Explain log: `data/explain_logs/explain_2026-06-08.json`
- Report: `data/reports/report_2026-06-08.json`
- Generated outputs committed: false

## Scope note

This is a sanitized 50-stock OpenDART smoke with an FDR/cache-backed universe, `max_universe_size=50`, and `request_delay_seconds=0.2`.
It is not a full-market live verification.
