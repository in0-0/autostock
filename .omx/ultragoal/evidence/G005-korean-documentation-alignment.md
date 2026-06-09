# G005 Korean Documentation Alignment Evidence

## Story
`G005-korean-documentation-alignment-after`

## Files changed
- `README.md`
  - Reframed AutoStock as a weekend candidate-review service centered on read-only Google Sheets input and candidate review notes.
  - Removed stale next-step emphasis on broker connectors and scheduling.
  - Documented report/explain structured `review_notes` outputs and current non-goals without secret values or private portfolio data.
- `docs/STATUS.md`
  - Updated date/status to 2026-06-10 KST and candidate review-note final-verification state.
  - Added current implementation status for structured review notes in report/explain artifacts.
  - Recorded that `peg_macro_v1` scoring semantics were not changed.
- `docs/ROADMAP.md`
  - Updated product baseline to Google Sheets weekend candidate review-note service.
  - Added completed v0.2 review-note goals and release gates.
  - Clarified near-miss note expansion as a future product decision outside first pass.

## Verification
- `git diff --check` passed.
- Documentation exact-phrase scan passed:
  - `! rg -n '자동 주문|매수 수량|목표 비중|자동 리밸런싱|주문 실행|한국투자|키움|broker connector' README.md docs/STATUS.md docs/ROADMAP.md`
- Documentation secret-key scan passed:
  - `! rg -n 'bot_token|chat_id|spreadsheet_id|credentials_path|token_path|account_id|계좌번호' README.md docs/STATUS.md docs/ROADMAP.md`

## Notes
- No generated runtime data or live credential values were added.
- This was documentation-only; the full code test suite already passed in G004 and will be rerun in the final gate.
