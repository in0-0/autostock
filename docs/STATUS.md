# 프로젝트 상태

**마지막 갱신:** 2026-06-08
**상태:** v0.2.0 서비스 스펙 구현 검증 중
**현재 버전:** v0.1.0 (개발 중)

## 현재 제품 정의

AutoStock은 Google Sheets에 있는 개인 포트폴리오를 주말마다 점검하고,
KOSPI/KOSDAQ 전체 종목 중 재무제표와 가격/거래량 데이터가 충분한 기업을
분석해 매수 후보 리뷰 목록을 만들며, 결과를 Telegram으로 전달하는 로컬 우선
배치 서비스다.

현재 단계에서는 후보 목록만 제공한다. 자동 주문, 매수 수량 계산, 목표 비중,
자동 리밸런싱, 실증권사 API 연결은 하지 않는다.

## 버전 계획

> 과거 릴리스는 [HISTORY.md](./HISTORY.md)를 기준으로 한다.

| 버전 | 초점 | 상태 |
|------|------|------|
| **v0.1.0** | 로컬 CLI, mock/sample 기반 회귀 테스트, JSON 아티팩트 저장 | 개발 기준선 |
| **v0.2.0** | Google Sheets 기반 주말 후보 리뷰 MVP | 다음 목표 |
| **v0.3.0** | 운영 스케줄, Telegram 재시도, runbook, 운영 안전성 | 이후 |

## 시스템 상태

| 영역 | 상태 | 확인 기준 |
|------|------|-----------|
| CLI 파이프라인 | 사용 가능 | `python3 -m src.main --settings config/settings.yaml` |
| 회귀 테스트 | 사용 가능 | `python3 -m pytest` |
| Google Sheets 입력 | 구현됨 | 읽기 전용 parser, CSV/TSV fixture, source-neutral portfolio boundary |
| 포트폴리오 병합 | 구현됨 | 같은 티커의 행을 통합하고 source warning을 기록 |
| 가격 데이터 | 구현 보강 / bounded smoke 통과 | sample/fixture/real 모드, pykrx/FDR fallback, cache/telemetry, bounded real smoke에서 pykrx 가격 provider 완료 및 FDR universe fallback 확인 |
| 재무제표 데이터 | 구현됨 / 결정적 coverage 보강 완료 | OpenDART 정규화 provider, corp-code cache, field provenance, missing-field exclusion 구현; DART `status:013`은 원시 taxonomy `provider_failed:opendart:dart_status:013`로 유지하며, 회귀 테스트로 provider 단계와 `_apply_financial_data` 전파를 고정했다. 전체 시장 live coverage 검증은 아직 별도 증거가 필요하다 |
| 후보 리포트 | 구현됨 | 근거, 리스크, provider 출처, 점수, 점수 입력값 기록 |
| 매크로 정책 | 구현됨 | `RISK_OFF` 차단, `CAUTION` 감점/리스크 표시, 매크로 데이터 부족 컨텍스트 기록 |
| Telegram | 구현됨 / live send 보류 | Markdown 렌더링, 실제 전송 시도, `sent`/`failed:<redacted>`/`disabled` 상태 기록; 2026-06-03 smoke에서는 credential 제거 상태로 `disabled` 확인 |
| 증권사 연동 | 현재 범위 밖 | mock connector는 기준선/호환 경로로만 유지 |
| 런타임 출력 | 구현됨 | `data/portfolio_state.json`, `data/reports/`, `data/explain_logs/` |

## 열린 이슈

| 우선순위 | 항목 | 이유 |
|----------|------|------|
| P0 | OpenDART full-market live coverage 확인 | `dart_status:013`은 코드 오류가 아니라 OpenDART 응답/데이터 coverage 이슈로 해석하도록 문서화하고 회귀 테스트로 raw taxonomy를 고정했다. 다만 전체 시장 live 검증은 G003에서 기존 비추적 로컬 설정과 rate-limit 조건이 안전할 때만 별도 수행한다 |
| P1 | 실제 Google Sheets/Telegram credential smoke | 이번 pass의 비목표다. 로컬 비추적 credential이 준비된 뒤 별도 test sheet/test chat으로 확인한다 |
| P2 | sample/fixture 설정과 개인 운영 설정 분리 | 실데이터 실행에서 샘플 대체를 방지해야 함 |

## 최근 변경

- 서비스 정체성을 Google Sheets 기반 주말 후보 리뷰 서비스로 정리했다.
- 현재 단계의 비목표를 명확히 했다: 실증권사 API, 자동 주문, 수량 계산, 목표 비중, 자동 리밸런싱 제외.
- v0.2.0 범위를 KOSPI/KOSDAQ 전체 후보 탐색, 재무제표/가격 데이터 완성도, explain log, Telegram 검증 중심으로 재정렬했다.
- 기존 mock broker 기반 흐름은 제품 중심이 아니라 로컬 회귀 테스트와 호환 기준선으로 재해석했다.
- 매크로 데이터 부족은 샘플 대체나 전역 위험 차단이 아니라 `CAUTION` 컨텍스트로 기록하고 후보 점수에 감점한다.
- 후보 순위는 재현 가능한 `review_score`, `score_policy_version`, `score_inputs`를 explain log와 리포트에 남긴다.
- Telegram 전송 상태는 실행 산출물에 `disabled`, `sent`, `failed:<redacted>` 중 하나로 남긴다.
- KOSPI/KOSDAQ universe provider, OpenDART 재무 정규화, provider별 cache/freshness 정책, exclusion count 리포팅을 추가했다.
- 2026-06-08 KST에 OpenDART DART `status:013` 회귀 테스트를 추가해 provider 결과와 `_apply_financial_data` 전파가 모두 `provider_failed:opendart:dart_status:013`를 유지하도록 고정했다. 이 값은 기계 판별용 원시 taxonomy이며, 사용자 문서에서는 “OpenDART가 해당 종목/기간 재무제표 데이터를 제공하지 않음”으로 해석한다.

- 2026-06-03 KST에 `max_universe_size=5` provider smoke를 비추적 로컬 설정(`config/settings.provider-smoke.local`)으로 실행했다. 초기 env-only run은 OpenDART key를 찾지 못했지만, 이후 `config/settings.local.yaml`의 로컬 YAML key를 값 출력 없이 반영해 재실행했다. 보정 run 결과는 pykrx 가격 provider 완료, FDR universe fallback 5종목, 매크로 데이터 부족에 따른 `CAUTION`, Telegram `disabled`, OpenDART credential path 확인, `dart_status:013`/재무 입력 부족 exclusion 기록이었다.
- Google Sheets live read와 Telegram live send는 이번 release-confidence pass의 비목표로 남겼고, 실제 credential 없이 실행하지 않았다.

## 다음 작업

v0.2.0의 주요 데이터-source 결정은 pykrx/FDR + OpenDART 경로로 구현됐고, bounded real smoke에서 pykrx 가격 provider, FDR universe fallback, OpenDART credential path가 확인됐다. `dart_status:013`은 provider/data coverage 관점의 exclusion으로 해석하고 raw taxonomy는 `provider_failed:opendart:dart_status:013` 그대로 유지한다. 결정적 회귀 테스트와 문서 보강은 완료됐지만, 전체 시장 OpenDART live coverage는 아직 검증 완료로 표시하지 않는다. 실제 Google Sheets 읽기와 Telegram test chat 발송은 이번 pass에서는 제외한 P1 검증으로 남긴다. 운영 스케줄, 재시도, runbook은 v0.3.0 범위로 넘긴다.
