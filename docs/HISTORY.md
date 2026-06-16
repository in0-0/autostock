# Release History

## v0.2.0 (2026-06-16)

Google Sheets 기반 주말 후보 리뷰 MVP를 릴리즈했다.

### Changes
| Change | Details |
|--------|---------|
| Google Sheets 포트폴리오 입력 | 읽기 전용 Google Sheets source와 동일 parser 경로의 CSV/TSV fixture를 지원한다. |
| KOSPI/KOSDAQ 후보 탐색 | pykrx/FDR 가격 provider fallback, 유니버스 filter/cache, OpenDART 재무 정규화 provider를 사용한다. |
| 보수적 후보 승격 | 재무제표, 가격/거래량, PEG, freshness, source risk가 부족한 종목은 후보에서 제외하고 explain log에 사유를 남긴다. |
| 매크로 정책 | `NORMAL`, `CAUTION`, `RISK_OFF` 정책을 점수/리스크/전역 차단 동작에 반영한다. |
| 후보 검토 메모 | 후보별 검토 이유, 보류/확인 사유, 다음 확인, 데이터 신뢰도, source/generated context를 report/explain에 저장한다. |
| Telegram 상태 기록 | Telegram 전송 결과를 `disabled`, `sent`, `failed:<redacted>` 중 하나로 report/explain에 기록한다. |
| 로컬 아티팩트 | `portfolio_state.json`, `explain_YYYY-MM-DD.json`, `report_YYYY-MM-DD.json`을 atomic write로 저장한다. |
| QA 증거 | 2026-06-16 KST 기준 `python3 -m pytest` 79개 테스트, sample/mock CLI smoke, runtime artifact 구조 확인, 산출물 안전 스캔을 통과했다. |

### Known follow-ups
- 실제 Google Sheets live read와 Telegram test chat send는 credential이 필요한 P1 운영 smoke로 남긴다.
- Public KOSPI/KOSDAQ universe provider full-load 실패는 v0.3 운영 리스크 관리 항목으로 유지한다.
- 운영 스케줄, Telegram retry, runbook, 설정 분리는 v0.3.0 범위에서 다룬다.

---

## Release Candidates

- 2026-06-16: v0.2.0-rc.1 후보를 정리했다.
  Google Sheets 기반 주말 후보 리뷰 MVP의 구현 범위를 유지하고,
  `python3 -m pytest` 79개 테스트, sample/mock CLI smoke, runtime artifact 구조 확인,
  산출물 안전 스캔을 통과했다.
  실제 Google Sheets live read와 Telegram test chat send는 credential이 필요한 P1 운영 smoke로 남긴다.

---

This file is updated by the `release` skill when versions are released.
