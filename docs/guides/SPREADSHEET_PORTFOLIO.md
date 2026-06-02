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
2. `portfolio_source.type`이 `google_sheets`인지 확인한다.
3. `portfolio_source.google_sheets.spreadsheet_id`에 시트 ID를 넣는다.
4. Google service-account JSON을 `config/google-service-account.local.json`에 저장한다.
5. 서비스 계정 이메일에 시트 viewer 권한을 준다.
6. `market_data.mode`가 의도한 실행 모드인지 확인한다.
7. 실제 시장 데이터 smoke에서는 `market_data.universe_provider.max_universe_size`를
   먼저 작게 둔다. 전체 KOSPI/KOSDAQ을 처리하려면 이 값을 `null`로 바꾸되,
   `request_delay_seconds`와 `cache_dir`를 반드시 유지한다.
8. OpenDART 재무제표를 사용하려면 `financial_data.provider: opendart`와
   `dart_api_key_env: AUTOSTOCK_DART_API_KEY`를 확인하고, 키는 YAML에 쓰지 말고
   환경 변수로 주입한다.
9. 다음 명령을 실행한다.

```bash
python3 -m src.main --settings config/settings.local.yaml
```

Google Sheets credential을 입력해도 `portfolio_source.type: broker_mock`이면 시트를
읽지 않고 mock portfolio를 사용한다. Telegram credential을 입력해도 분석 데이터
소스는 바뀌지 않으며, 생성된 리포트를 전송만 한다.

샘플 분석이 Telegram으로 발송되는 것을 막으려면 다음 두 축을 별도로 확인한다.

```yaml
portfolio_source:
  type: google_sheets
  google_sheets:
    spreadsheet_id: "..."
    range: "Portfolio!A:AF"
    credentials_path: "config/google-service-account.local.json"

market_data:
  mode: real
  universe: []
  universe_provider:
    enabled: true
    markets: [KOSPI, KOSDAQ]
    exclude_etf: true
    exclude_etn: true
    exclude_konex: true
    max_universe_size: 50
  cache_dir: "data/market_cache"
  request_delay_seconds: 0.2

financial_data:
  provider: opendart
  dart_api_key: ""
  dart_api_key_env: AUTOSTOCK_DART_API_KEY
  reprt_code: "11011"
```

`portfolio_source`는 보유 포트폴리오 입력을 결정하고, `market_data`는 후보 분석에
쓰는 가격/재무/매크로 데이터를 결정한다. `market_data.mode: sample`이면 Google
Sheets에서 보유 종목을 읽더라도 시장 데이터는 샘플로 분석된다.

라이브 Google credential 없이 로컬 smoke test를 할 때는
`portfolio_source.google_sheets.fixture_path`에 같은 헤더를 가진 CSV 또는 TSV 파일을
지정한다. 이 경로도 Google Sheets와 같은 parser를 사용하지만 Google client 호출은
건너뛴다. `market_data.mode: fixture`와 market-data JSON을 함께 쓰면 재현 가능한
CLI 검증을 할 수 있다.

## 실행 전 점검

민감값을 출력하지 않고 실행 모드만 확인하려면 다음 명령을 사용한다.

```bash
python3 - <<'PY'
from pathlib import Path
import yaml

settings = yaml.safe_load(Path("config/settings.local.yaml").read_text()) or {}
portfolio_source = settings.get("portfolio_source", {})
google_sheets = portfolio_source.get("google_sheets", {}) or {}
market_data = settings.get("market_data", {})
telegram = settings.get("telegram", {})

print("portfolio_source.type =", portfolio_source.get("type"))
print("google_sheets.spreadsheet_id set =", bool(google_sheets.get("spreadsheet_id")))
print("google_sheets.credentials_path set =", bool(google_sheets.get("credentials_path")))
print("market_data.mode =", market_data.get("mode"))
print("market_data.universe count =", len(market_data.get("universe") or []))
print("market_data.universe_provider.enabled =", (market_data.get("universe_provider") or {}).get("enabled"))
print("market_data.universe_provider.max_universe_size =", (market_data.get("universe_provider") or {}).get("max_universe_size"))
print("market_data.cache_dir set =", bool(market_data.get("cache_dir")))
financial_data = settings.get("financial_data", {})
print("financial_data.provider =", financial_data.get("provider"))
print("financial_data.dart_api_key_env =", financial_data.get("dart_api_key_env"))
print("telegram.bot_token set =", bool(telegram.get("bot_token")) and "REPLACE_WITH" not in str(telegram.get("bot_token")))
print("telegram.chat_id set =", bool(telegram.get("chat_id")) and "REPLACE_WITH" not in str(telegram.get("chat_id")))
PY
```

실제 Google Sheets와 실제 시장 데이터로 실행하려는 경우 기대값은
`portfolio_source.type = google_sheets`, `market_data.mode = real`,
`financial_data.provider = opendart`, `financial_data.dart_api_key_env = AUTOSTOCK_DART_API_KEY`,
`telegram.bot_token set = True`, `telegram.chat_id set = True`다.

라이브 시장 provider를 사용할 때는 `market_data.universe`를 작게 제한하고
`market_data.request_delay_seconds`로 티커별 호출 간격을 둔다. 마지막 성공 응답을
재사용하려면 `market_data.cache_dir`를 설정하고, stale 가격이 현재 스크리닝 데이터로
오인되지 않도록 `market_data.cache_max_age_days`를 짧게 유지한다.
`market_data.universe: []`인 경우 `universe_provider`가 KOSPI/KOSDAQ 유니버스를
해석한다. OpenDART는 해석된 유니버스의 각 티커에 대해 corp-code mapping이 있으면
재무제표 조회를 시도하고, 키가 없으면 각 티커가 `dart_api_key_missing` 제외 사유로
기록된다.

OpenDART 키는 다음처럼 환경 변수로만 주입한다.

```bash
export AUTOSTOCK_DART_API_KEY="..."
python3 -m src.main --settings config/settings.local.yaml
```

로컬 smoke를 넘어 전체 유니버스를 처리하려면 `max_universe_size: null`로 바꾸면 된다.
다만 전체 KOSPI/KOSDAQ은 provider 호출 수가 크므로 cache와 지연 설정 없이 실행하지
않는다.

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
