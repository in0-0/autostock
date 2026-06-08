# OpenDART Coverage Hardening 기록 (2026-06-08 KST)

## 결론

OpenDART DART 응답 `status:013`은 AutoStock 내부에서 원시 제외 사유
`provider_failed:opendart:dart_status:013`로 유지한다. 이 값은 리포트와 explain
log가 같은 원인을 재현 가능하게 집계하기 위한 기계 판별용 taxonomy다.

사용자 문서와 운영 해석에서는 이를 “OpenDART가 해당 종목/사업연도/보고서 조합의
재무제표 데이터를 제공하지 않았거나 coverage가 비어 있음”으로 설명한다. 점수 산식,
후보 선정 전략, provider 종류는 변경하지 않았다.

## 이번 보강 범위

- DART `status:013` 응답이 provider 단계에서 crash 없이
  `provider_failed:opendart:dart_status:013`로 기록되는지 회귀 테스트로 고정했다.
- `_apply_financial_data` 경로에서도 같은 제외 사유가 `MarketDataBundle.exclusion_reasons`에
  전파되는지 명명된 테스트로 고정했다.
- 기존 `missing_*` 재무 입력 부족 exclusion은 그대로 유지한다.
- Google Sheets live read, Telegram live send, 증권사 주문/리밸런싱/매수 수량 산정은
  이번 범위가 아니다.

## 검증 상태

- 결정적 테스트 보강: 완료.
- 전체 회귀 테스트: 통과.
- 50종목 OpenDART live smoke: 2026-06-08 KST에 FDR/cache-backed 50종목 universe, `request_delay_seconds=0.2`, Telegram/Google Sheets disabled 조건으로 완료했다. 결과는 `provider_failed:opendart:dart_status:013` 19건과 재무 입력 부족 exclusion을 sanitized evidence로 기록했다.
- 전체 시장 전체 종목 live coverage: 아직 완료로 표시하지 않는다. 별도 운영 검증으로 남긴다.

## 운영자 참고

리포트에서 `provider_failed:opendart:dart_status:013`가 상위 제외 사유로 보이면,
AutoStock 코드가 실패했다는 의미로 단정하지 않는다. 먼저 대상 종목, 사업연도,
보고서 코드 조합에서 OpenDART가 실제로 재무제표 rows를 제공하는지 확인한다.
이 raw taxonomy는 자동 점수 정책을 바꾸지 않고 coverage 원인을 추적하기 위해 유지한다.
