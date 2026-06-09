# G003 Report and Artifact Integration Evidence

## Story
`G003-report-and-artifact-integration-rend`

## Files changed
- `src/main.py`
  - Builds `Candidate.review_note` for ranked candidates after ranking, without altering ranking/scoring inputs.
  - Persists structured `review_note` payloads in both report JSON (`review_notes`) and explain-log candidate items.
  - Preserves `telegram_delivery_status`, explain audit fields, provider metadata, and warning payloads.
- `src/reporting.py`
  - Renders structured Korean candidate review notes under `💰 후보 검토 메모`.
  - Uses review/defer/check language (`검토 이유`, `보류/확인 사유`, `다음 확인`, `데이터 신뢰도`).
  - Adds no-candidate guidance from top exclusion categories only.

## Verification
- `python3 -m py_compile src/main.py src/reporting.py src/models.py src/review_notes.py` passed.
- `rg -n 'print\(api_key\)|print\(candidate\)' src/main.py src/reporting.py` returned no matches.
- Non-live default CLI smoke passed:
  - `python3 -m src.main --settings config/settings.yaml > /tmp/autostock-g003-smoke.out`
  - Generated `data/reports/report_2026-06-10.json` and `data/explain_logs/explain_2026-06-10.json`.
  - Runtime emitted an existing urllib3 LibreSSL environment warning; no task-blocking error.
- Smoke artifact checks:
  - Telegram delivery remained disabled in report JSON.
  - Report JSON contains `review_notes` for 6 candidates.
  - Explain log contains 6 candidate items with non-null `review_note`.
  - Review note keys include `review_reason`, `defer_or_reject_reason`, `next_check`, `data_confidence`, `source_context`, `generated_context`, and `excluded_or_near_miss_context`.
- Forbidden output scan over the smoke output and generated report/explain artifacts returned no matches for order/sizing/rebalancing/credential terms:
  - `매수 수량`, `목표 비중`, `자동 주문`, `리밸런싱`, `주문 실행`
  - `bot_token`, `chat_id`, `spreadsheet_id`, `credentials_path`, `token_path`

## Notes
Generated files under `data/` are runtime artifacts and are intentionally not staged for commit.
