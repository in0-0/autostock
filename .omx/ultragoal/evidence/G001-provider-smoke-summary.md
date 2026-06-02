# G001 Provider Smoke Evidence

- Settings profile: `config/settings.provider-smoke.local` (ignored/untracked)
- Command shape: `env -u AUTOSTOCK_TELEGRAM_BOT_TOKEN -u AUTOSTOCK_TELEGRAM_CHAT_ID python3 -m src.main --settings config/settings.provider-smoke.local`
- Market data provider: `pykrx`
- Macro provider: `unavailable`
- Telegram delivery status: `disabled`
- OpenDART status: `blocked:dart_api_key_missing`
- Universe snapshot: `{'source': 'fdr_universe', 'source_risk': 'package_public_source', 'count': 5, 'markets': ['KOSPI', 'KOSDAQ'], 'collected_at': '2026-06-03T00:27:36.178426'}`
- Exclusion counts: `{'dart_api_key_missing': 5}`
- Explain log: `data/explain_logs/explain_2026-06-03.json`
- Report: `data/reports/report_2026-06-03.json`

## Warnings

- `universe_provider_failed:pykrx_universe:index -1 is out of bounds for axis 0 with size 0`
- `macro_data_unavailable:pykrx`
- `dart_api_key_missing`

## Notes

- OpenDART API was not called because AUTOSTOCK_DART_API_KEY was absent; dart_api_key_missing was recorded as blocker evidence.
- Bounded real-mode provider smoke completed with max_universe_size=5 and Telegram disabled.
- pykrx universe provider emitted a sanitized failure warning; market data provider completed as shown in explain log.
