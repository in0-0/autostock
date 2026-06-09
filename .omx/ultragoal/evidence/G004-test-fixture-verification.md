# G004 Test and Fixture Verification Evidence

## Story
`G004-test-and-fixture-verification-add-fo`

## Test coverage added
- `tests/test_phase1.py`
  - Added builder coverage for passing candidate notes with risk, macro, provider, score-input, and data-warning context.
  - Extended no-candidate report coverage to assert top-exclusion follow-up guidance.
  - Added structured report-rendering coverage for `검토 이유`, `보류/확인 사유`, `다음 확인`, and `데이터 신뢰도` lines.
  - Added Telegram MarkdownV2 escaping coverage for review-note text containing `_`, `[ ]`, and `( )`.
  - Added static regression coverage for removed debug leaks and current-stage order/sizing language.
  - Extended CLI fixture smoke tests so report JSON and explain-log items must include structured `review_note` fields.
  - Preserved existing `peg_macro_v1` scoring semantics coverage; tests still assert the same `review_score`, `score_policy_version`, macro status, and macro penalty values.

## Verification commands
- Targeted pytest subset passed:
  - `python3 -m pytest tests/test_phase1.py -k 'review_note or report_shows_top_exclusion_counts or cli_with_spreadsheet_and_market_fixtures or cli_with_missing_fixture_macro or candidate_ranking_records_score_inputs or changed_source_has_no_debug'`
  - Result: 8 passed, 59 deselected, 1 urllib3 LibreSSL environment warning.
- Full test suite passed:
  - `python3 -m pytest`
  - Result: 67 passed, 15 environment/dependency warnings.
- Whitespace/diff validation passed:
  - `git diff --check`
- Targeted runtime source scans passed:
  - `! rg -n 'print\(api_key\)|print\(candidate\)' src/main.py src/reporting.py`
  - `! rg -n '매수 수량|목표 비중|자동 주문|리밸런싱|주문 실행' src/main.py src/reporting.py`
  - `! rg -n 'bot_token|chat_id|spreadsheet_id|credentials_path|token_path' src/reporting.py`

## Notes
- The broad test-file scan initially matched the test assertions' own forbidden-string fixtures; the durable verification scope was corrected to runtime source and renderer surfaces to avoid false positives.
- No live Google Sheets, Telegram send, or external credentials were used.
