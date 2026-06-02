# G001 Supplemental Provider Smoke Evidence - Local OpenDART Key Rerun

- Settings profile: `config/settings.provider-smoke.local` (ignored/untracked)
- Local key source: `config/settings.local.yaml` `financial_data.dart_api_key` (presence checked only; value not printed)
- Command shape: `env -u AUTOSTOCK_TELEGRAM_BOT_TOKEN -u AUTOSTOCK_TELEGRAM_CHAT_ID python3 -m src.main --settings config/settings.provider-smoke.local`
- Market data provider: `pykrx`
- Macro status: `CAUTION`
- Macro provider: `unavailable`
- Telegram delivery status: `disabled`
- OpenDART status: `exercised:credential_path_no_dart_api_key_missing`
- Universe snapshot: `{'source': 'fdr_universe', 'source_risk': 'package_public_source', 'count': 5, 'markets': ['KOSPI', 'KOSDAQ'], 'collected_at': '2026-06-03T00:27:36.178426'}`
- Exclusion counts: `{'missing_peg_inputs': 4, 'missing_net_income_growth_inputs': 1, 'missing_roe_inputs': 1, 'provider_failed:opendart:dart_status:013': 1}`
- Explain log: `data/explain_logs/explain_2026-06-03.json`
- Report: `data/reports/report_2026-06-03.json`

## Warnings

- `universe_provider_failed:pykrx_universe:index -1 is out of bounds for axis 0 with size 0`
- `macro_data_unavailable:pykrx`

## Notes

- The first env-only smoke reported `dart_api_key_missing`; this supplemental rerun corrected the input source by using the non-tracked local YAML key.
- `dart_api_key_missing` is no longer present in exclusion counts.
- Remaining OpenDART-related evidence is `provider_failed:opendart:dart_status:013` for one ticker plus financial scoring input gaps for other bounded-universe tickers.
- Google Sheets live read and Telegram live send remained disabled/non-goals.
