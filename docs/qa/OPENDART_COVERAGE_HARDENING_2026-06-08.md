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
- 50종목 OpenDART live smoke: 2026-06-08 KST에 FDR/cache-backed 50종목 universe,
  `request_delay_seconds=0.2`, Telegram/Google Sheets disabled 조건으로 완료했다.
  결과는 `provider_failed:opendart:dart_status:013` 19건과 재무 입력 부족 exclusion을
  sanitized evidence로 기록했다.
- OpenDART full listed-company validation: 2026-06-09 KST에 OpenDART corp-code cache
  fallback universe 3,967건으로 완료했다. FDR full-universe load는 HTTP 404,
  pykrx full-universe load는 empty-index 오류로 실패했다. 따라서 이 증거는
  public KOSPI/KOSDAQ universe provider 성공이 아니라 OpenDART corp-code fallback 기반
  full listed-company DART financial endpoint 검증으로 해석한다.

## 운영자 참고

리포트에서 `provider_failed:opendart:dart_status:013`가 상위 제외 사유로 보이면,
AutoStock 코드가 실패했다는 의미로 단정하지 않는다. 먼저 대상 종목, 사업연도,
보고서 코드 조합에서 OpenDART가 실제로 재무제표 rows를 제공하는지 확인한다.
이 raw taxonomy는 자동 점수 정책을 바꾸지 않고 coverage 원인을 추적하기 위해 유지한다.


## Full listed-company validation 추가 기록 (2026-06-09 KST)

안전 경계는 다음과 같았다.

- 기존 비추적 로컬 설정 또는 환경에서 OpenDART key 존재 여부만 확인하고 key 값은 출력하지 않았다.
- Google Sheets live read와 Telegram live send는 실행하지 않았다.
- DART financial API 호출은 cache를 사용하고 호출 사이에 최소 0.2초 지연을 적용했다.
- 생성된 runtime cache와 `.omx/evidence/` 원본 증거는 커밋 대상이 아니다.

관찰 결과는 다음과 같다.

| 항목 | 결과 |
|------|------|
| universe provider | `opendart_corp_code_fallback` |
| universe count | 3,967 |
| FDR full-universe load | `HTTP Error 404: Not Found` |
| pykrx full-universe load | `index -1 is out of bounds for axis 0 with size 0` |
| DART financial API calls | 3,936 |
| request delay | 0.2초 이상 |
| normalized fundamentals | 0 |
| excluded tickers | 3,967 |
| top provider failure | `provider_failed:opendart:dart_status:013` 1,754건 |
| top missing input | `missing_peg_inputs` 2,213건 |
| targeted regression | `python3 -m pytest tests/test_phase1.py -k "dart_status or missing_peg_inputs or apply_financial_data"` → 4 passed |

해석:

- `provider_failed:opendart:dart_status:013`와 `missing_*` exclusion은 기존 회귀 테스트와
  같은 stable taxonomy로 유지됐다.
- 직접 OpenDART 검증은 market PER 지표를 붙이지 않았기 때문에 `fundamentals_count`가 0이었다.
  이는 이번 evidence run의 한계이며, taxonomy propagation bug로 보지 않는다.
- OpenDART coverage 공백은 v0.2 blocker가 아니라 문서화된 잔여 리스크로 둔다.
- FDR/pykrx full-universe provider 오류는 OpenDART taxonomy 오류와 별개인 universe provider 운영 리스크다.
