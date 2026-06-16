# v0.2.0 릴리즈 후보 QA

**일시:** 2026-06-16 KST
**범위:** v0.2.0 Google Sheets 기반 주말 후보 리뷰 MVP 릴리즈 후보 검증
**결론:** 통과. 현재 코드와 sample/mock 실행 경로는 v0.2.0 릴리즈 후보로 정리할 수 있다.

## 실행 결과

| 영역 | 결과 | 상세 |
|------|------|------|
| 회귀 테스트 | PASS | `python3 -m pytest`에서 79개 테스트 통과 |
| CLI smoke | PASS | `python3 -m src.main --settings config/settings.yaml` exit 0 |
| 산출물 구조 | PASS | `portfolio_state.json`, `explain_2026-06-16.json`, `report_2026-06-16.json` 생성 확인 |
| 산출물 안전 스캔 | PASS | 주문/수량/목표비중/credential 패턴 match 없음 |
| Telegram 상태 | PASS | placeholder 설정에서 `disabled` 기록 |

## 산출물 확인

- portfolio positions: 2개
- portfolio partial success: `false`
- explain macro status: `NORMAL`
- market data provider: `sample`
- explain items: 6개
- report review notes: 6개
- score policy: `peg_macro_v1`
- review note fields: `review_reason`, `defer_or_reject_reason`, `next_check`, `data_confidence`, `source_context`, `generated_context`, `excluded_or_near_miss_context`

## 안전 스캔

다음 패턴으로 `data/` 산출물을 검사했고 match가 없었다.

```bash
rg -n "추가 매수|매수 수량|목표 비중|목표비중|자동 주문|리밸런싱|주문 실행|\\bBUY\\b|\\bSELL\\b|bot_token|chat_id|spreadsheet_id|credentials_path|token_path|/Users/|REPLACE_WITH|sk-[A-Za-z0-9]" data
```

## 남은 확인

- 실제 Google Sheets live read와 Telegram test chat 발송은 credential이 필요한 P1 운영 smoke로 남긴다.
- Public KOSPI/KOSDAQ universe provider full-load 실패는 v0.3 운영 리스크 관리 항목으로 유지한다.
- 운영 스케줄, Telegram retry, runbook, 설정 분리는 v0.3.0 범위에서 다룬다.
