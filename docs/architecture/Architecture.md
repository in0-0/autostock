# 아키텍처

AutoStock은 한국 주식 개인 포트폴리오를 주말마다 점검하고, KOSPI/KOSDAQ
전체 종목 중 분석 가능한 기업에서 매수 후보를 찾아 Telegram으로 전달하는
로컬 우선 Python 배치 서비스다.

현재 단계의 산출물은 후보 검토 목록이다. 증권사 API 연동, 자동 주문, 매수
수량 계산, 목표 비중 또는 리밸런싱 추천은 현재 범위가 아니다.

## 제품 경계

| 구분 | 결정 |
|------|------|
| 포트폴리오 입력 | Google Sheets를 읽기 전용으로 사용한다. |
| 후보 탐색 범위 | 현재 보유 종목만이 아니라 KOSPI/KOSDAQ 전체 종목을 대상으로 한다. |
| 후보 허용 조건 | 재무제표 데이터와 가격/거래량 데이터가 충분해야 한다. |
| 매크로 정책 | `NORMAL`은 영향 없음, `CAUTION`은 감점 또는 하향 표시, `RISK_OFF`는 후보 전체 차단. |
| 결과물 | 종목명, 티커, 점수/순위, 선정 근거, 리스크, 데이터 출처를 포함한 후보 리뷰. |
| 전달 채널 | Telegram Markdown 리포트와 로컬 JSON 아티팩트. |
| 제외 범위 | 주문 실행, 매수 수량, 목표 비중, 자동 리밸런싱, 현재 단계의 실증권사 연동. |

## 실행 흐름

```text
settings.yaml
  -> Google Sheets 포트폴리오 읽기 전용 수집
  -> KOSPI/KOSDAQ 유니버스 로딩
  -> 재무제표 + 가격/거래량 + 매크로 데이터 수집
  -> 데이터 완성도 검사와 제외 사유 기록
  -> 매크로 상태 정책 적용
  -> 재무/기술/리스크 기준 평가
  -> 후보 점수화와 순위 산정
  -> Telegram Markdown 리포트 생성
  -> portfolio state + explain log + report JSON 저장
```

## 주요 모듈

| 모듈 | 책임 |
|------|------|
| `src/main.py` | 설정을 읽고 전체 배치 실행을 오케스트레이션한다. |
| `src/collectors/google_sheets.py` | Google Sheets와 CSV/TSV fixture를 같은 파서 경로로 읽는다. |
| `src/collectors/portfolio_source.py` | 포트폴리오 입력 소스를 병합 가능한 내부 모델로 변환한다. |
| `src/collectors/market_data.py` | 시장 데이터 모드, provider fallback, 캐시, 데이터 완성도 경고를 처리한다. |
| `src/engines/macro.py` | 시장 상태를 `NORMAL`, `CAUTION`, `RISK_OFF`로 판정한다. |
| `src/engines/fundamental.py` | 재무 기준으로 후보 가능성을 평가한다. |
| `src/engines/technical.py` | 가격/거래량과 기술적 조건을 평가한다. |
| `src/engines/exit.py` | 보유 또는 후보 종목의 위험 신호를 계산한다. |
| `src/engines/portfolio.py` | 후보 순위, `review_score`, 점수 입력값을 산정한다. 기존 trade guide API는 Phase 1 호환 경로이며 v0.2 주 실행 경로에서는 호출하지 않는다. |
| `src/reporting.py` | 후보 근거, 리스크, 데이터 출처, 점수, Telegram 전송 상태를 포함한 Markdown을 렌더링한다. |
| `src/utils/atomic.py` | JSON 결과물을 atomic write로 저장한다. |
| `src/utils/telegram.py` | Telegram 전송 클라이언트를 제공한다. |

## 현재 구현과 목표 상태의 차이

| 영역 | 현재 상태 | 목표 상태 |
|------|-----------|-----------|
| 포트폴리오 입력 | Google Sheets 읽기 전용 파서와 fixture 경로가 있다. | Google Sheets가 기본 운영 입력으로 문서와 설정에서 우선된다. |
| 시장 가격 데이터 | sample, fixture, real 모드와 pykrx/FDR fallback, Naver stub가 있다. | KOSPI/KOSDAQ 전체 스크리닝에 충분한 가격/거래량 수집으로 확장한다. |
| 재무제표 데이터 | 샘플/fixture 중심이며 실제 전체 시장 커버리지는 미완성이다. | 재무제표 제공 기업을 식별하고, 재무 데이터가 충분한 종목만 후보화한다. |
| 매크로 정책 | `RISK_OFF` 차단, `CAUTION` 감점, 매크로 데이터 부족 컨텍스트 기록이 있다. | 라이브 매크로 provider 확장 시에도 같은 상태 계약을 유지한다. |
| 후보 리포트 | 근거, 리스크, provider 출처, 점수/순위 입력값, 제외 사유를 표시한다. | 라이브 전체 시장 스크리닝에서도 동일한 explain log 계약을 유지한다. |
| Telegram | Markdown 생성, 전송 시도, 성공/실패/비활성 상태 기록이 있다. | v0.3에서 재시도와 운영 실패 알림 정책을 강화한다. |
| 증권사 연동 | mock connector와 broker 경계가 남아 있다. | 현재 단계에서는 보조 호환 경로로만 취급하고 제품 중심에서 제외한다. |

## 설계 원칙

- Google Sheets는 읽기 전용 입력이어야 하며, 시트에 쓰거나 주문을 실행하지 않는다.
- 외부 API, 신규 패키지, 운영 스케줄 변경은 별도 확인 없이는 추가하지 않는다.
- 실제 데이터 실패를 샘플 데이터로 조용히 대체하지 않는다.
- 재무제표 또는 가격/거래량이 부족한 종목은 후보에서 제외하고 explain log에 사유를 남긴다.
- 매크로가 `RISK_OFF`이면 해당 실행의 후보 승격을 전역 차단한다.
- 매크로 데이터 자체가 부족한 경우에는 샘플 대체나 즉시 `RISK_OFF`가 아니라 `CAUTION` 컨텍스트와 감점으로 노출한다.
- 포트폴리오, 리포트, explain log는 로컬 JSON 아티팩트로 재현 가능해야 한다.
- 시트 ID, 계좌명, credential 경로, Telegram 토큰, 개인 포트폴리오 행은 문서/로그/테스트에 노출하지 않는다.
