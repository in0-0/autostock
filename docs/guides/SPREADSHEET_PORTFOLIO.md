# 스프레드시트 포트폴리오 입력

AutoStock은 Google Sheets를 주말 후보 리뷰 MVP의 읽기 전용 포트폴리오 입력으로
사용할 수 있다. 서비스는 시트를 읽고 채워진 보유 종목 행을 분석 입력으로만
사용한다. 시트에 값을 쓰거나 주문을 실행하지 않는다.

## 예상 컬럼

채워진 보유 종목 필드만 필요하며 선택 컬럼은 비워둘 수 있다. 같은 티커가 여러
행에 있으면 별도 계좌로 관리하지 않고 분석용 통합 포지션으로 병합한다.

권장 헤더:

```text
기준일, 증권사, 계좌명, 계좌유형, 시장, 종목코드, 종목명, 티커, 자산군, 섹터,
통화, 보유수량, 평균매수가, 현재가, 평가금액, 전체 포트폴리오 비중, 목표비중,
투자전략, 투자근거, 메모
```

파서는 `72,034` 같은 한국식 숫자, `11.01%` 같은 비율, `KRX:069500` 같은 티커
표기를 처리한다. `목표비중` 컬럼이 있어도 현재 단계에서는 분석 입력으로만
취급하며 목표 비중 추천이나 자동 리밸런싱을 생성하지 않는다.

## 로컬 설정

1. `config/settings.spreadsheet.example.yaml`을 `config/settings.local.yaml`로 복사한다.
2. `portfolio_source.google_sheets.spreadsheet_id`에 시트 ID를 넣는다.
3. Google service-account JSON을 `config/google-service-account.local.json`에 저장한다.
4. 서비스 계정 이메일에 시트 viewer 권한을 준다.
5. 다음 명령을 실행한다.

```bash
python3 -m src.main --settings config/settings.local.yaml
```

라이브 Google credential 없이 로컬 smoke test를 할 때는
`portfolio_source.google_sheets.fixture_path`에 같은 헤더를 가진 CSV 또는 TSV 파일을
지정한다. 이 경로도 Google Sheets와 같은 parser를 사용하지만 Google client 호출은
건너뛴다. `market_data.mode: fixture`와 market-data JSON을 함께 쓰면 재현 가능한
CLI 검증을 할 수 있다.

라이브 시장 provider를 사용할 때는 `market_data.universe`를 작게 제한하고
`market_data.request_delay_seconds`로 티커별 호출 간격을 둔다. 마지막 성공 응답을
재사용하려면 `market_data.cache_dir`를 설정하고, stale 가격이 현재 스크리닝 데이터로
오인되지 않도록 `market_data.cache_max_age_days`를 짧게 유지한다.

## 산출물과 상태

- `data/portfolio_state.json`: 병합된 포트폴리오와 입력 경고.
- `data/explain_logs/explain_YYYY-MM-DD.json`: 후보별 근거, 제외 사유, provider 출처, `review_score`, `score_inputs`.
- `data/reports/report_YYYY-MM-DD.json`: Telegram Markdown 본문과 `telegram_delivery_status`.

Telegram 설정이 없거나 placeholder 값이면 전송 상태는 `disabled`로 기록된다. 실제
전송 성공은 `sent`, 실패는 민감값이 제거된 `failed:<redacted>` 형식으로 남는다.

## 안전 규칙

- `config/settings.local.yaml`과 Google credential 파일은 로컬 전용으로 유지한다.
- Google Sheets scope는 readonly만 사용한다.
- 개인 행, 시트 ID, 계좌명, credential 경로, Telegram token/chat id를 이슈, 로그,
  스크린샷, Pull Request에 붙여 넣지 않는다.
- 시장 데이터 provider가 실패하면 리포트와 explain log에 실패를 표시하고, 불완전한
  후보를 조용히 승격하지 않는다.
