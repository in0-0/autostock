# 프로젝트 상태

**마지막 갱신:** 2026-06-16
**상태:** v0.2.0 릴리즈 완료
**현재 버전:** v0.2.0

## 현재 제품 정의

AutoStock은 Google Sheets에 있는 개인 포트폴리오를 주말마다 점검하고,
KOSPI/KOSDAQ 전체 종목 중 재무제표와 가격/거래량 데이터가 충분한 기업을 분석해
후보 검토 목록과 후보별 확인 메모를 만들며, 결과를 Telegram Markdown 리포트와
로컬 JSON 아티팩트로 남기는 로컬 우선 배치 서비스다.

현재 단계에서는 후보 목록과 검토 메모만 제공한다. 증권사 주문, 수량 산정,
비중 추천, 실증권사 API 연결은 하지 않는다.

## 버전 계획

| 버전 | 초점 | 상태 |
|------|------|------|
| **v0.2.0** | Google Sheets 기반 주말 후보 리뷰 MVP | 릴리즈 완료 |
| **v0.3.0** | 운영 스케줄, Telegram 재시도, runbook, 운영 안전성 | 다음 목표 |

## 시스템 상태

| 영역 | 상태 | 확인 기준 |
|------|------|-----------|
| CLI 파이프라인 | 사용 가능 | `python3 -m src.main --settings config/settings.yaml` |
| 회귀 테스트 | 사용 가능 | `python3 -m pytest` |
| Google Sheets 입력 | 구현됨 | 읽기 전용 parser, CSV/TSV fixture, source-neutral portfolio boundary |
| 가격 데이터 | 구현됨 / bounded smoke 통과 | sample/fixture/real 모드, pykrx/FDR fallback, cache/telemetry |
| 재무제표 데이터 | 구현됨 / OpenDART evidence 확인 | OpenDART 정규화 provider, corp-code cache, field provenance, missing-field exclusion |
| 후보 리포트 | 구현됨 | 근거, 리스크, provider 출처, 점수 입력값, 구조화 검토 메모 기록 |
| 매크로 정책 | 구현됨 | `RISK_OFF` 차단, `CAUTION` 감점/리스크 표시, 매크로 데이터 부족 컨텍스트 기록 |
| Telegram | 구현됨 / live send 보류 | Markdown 렌더링, `sent`/`failed:<redacted>`/`disabled` 상태 기록 |
| 런타임 출력 | 구현됨 | `data/portfolio_state.json`, `data/reports/`, `data/explain_logs/` |

## 최근 변경

- 2026-06-16 KST에 v0.2.0을 릴리즈했다.
  릴리즈 직전 `python3 -m pytest`는 79개 테스트 통과,
  `python3 -m src.main --settings config/settings.yaml`는 exit 0으로 완료됐다.
  생성 산출물은 `NORMAL`, provider `sample`, Telegram `disabled`, 후보 6개와
  `peg_macro_v1` score policy를 기록했고, `data/` 안전 스캔에서 주문/수량/목표비중/credential
  패턴은 발견되지 않았다.

## 다음 작업

v0.3.0 운영 안정화로 넘어간다.

1. 주말 실행 runbook, 롤백 절차, 검증 체크리스트를 문서화한다.
2. sample/fixture 설정과 개인 운영 설정을 더 명확히 분리한다.
3. Telegram 전송 재시도와 실패 알림 정책을 강화한다.
4. provider rate limit, stale cache, 부분 실패 기준을 운영 로그와 explain log에 명확히 남긴다.

실제 Google Sheets live read와 Telegram test chat 발송은 로컬 비추적 credential이 준비된 뒤
별도 P1 운영 smoke로 수행한다.
