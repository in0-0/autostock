# 서비스 스펙 QA 실행 가이드

이 문서는 AutoStock v0.2 서비스 스펙 구현을 사용자가 로컬에서 재검증하는 절차다.
실제 credential 없이 재현 가능한 fixture 경로를 먼저 확인하고, credential이 준비된
경우에만 선택적으로 live smoke를 실행한다.

## 1. 기본 회귀 테스트

저장소 루트에서 실행한다.

```bash
python3 -m pytest
```

기대 결과:

- `38 passed`
- macOS 기본 Python에서는 `urllib3` LibreSSL warning이 나올 수 있다. 테스트 실패가
  아니면 QA 실패로 보지 않는다.

## 2. 샘플 설정 CLI smoke

기본 sample/mock 경로가 끝까지 실행되는지 확인한다.

```bash
python3 -m src.main --settings config/settings.yaml
```

확인할 산출물:

- `data/portfolio_state.json`
- `data/explain_logs/explain_YYYY-MM-DD.json`
- `data/reports/report_YYYY-MM-DD.json`

확인할 내용:

- 리포트가 후보 검토 목록과 시스템 리스크 경고를 출력한다.
- `report_YYYY-MM-DD.json`에 `telegram_delivery_status`가 있다.
- 자동 주문, 매수 수량, 목표 비중 추천, 자동 리밸런싱 지시가 리포트에 나오지 않는다.

## 3. Google Sheets fixture 기반 smoke

라이브 Google credential 없이 같은 parser 경로를 검증하려면 임시 CSV와 market fixture를
만든 뒤 `portfolio_source.google_sheets.fixture_path`와 `market_data.fixture_path`를
가리키는 로컬 설정 파일을 사용한다.

최소 포트폴리오 CSV 예:

```csv
종목코드,종목명,보유수량,평균매수가,현재가,평가금액
069500,KODEX 200,51,"72,034",130600,"6,660,600"
```

최소 확인 기준:

- 정상 macro fixture: explain log의 `macro_status`가 `NORMAL`.
- partial macro fixture: explain log의 `macro_status`가 `CAUTION`, 후보 risks에
  `macro_caution_penalty`.
- `RISK_OFF` macro fixture: 후보 `final_rank`가 `null`, risks에 `macro_risk_off`.
- current price 누락: 후보 `final_rank`가 `null`, risks에 `missing_current_price`.
- 모든 실행에서 `score_inputs.score_policy_version`은 `peg_macro_v1`.

## 4. Telegram 상태 확인

credential이 없거나 placeholder 값이면 정상적으로 비활성 처리된다.

```yaml
telegram:
  bot_token: "REPLACE_WITH_LOCAL_TELEGRAM_BOT_TOKEN"
  chat_id: "REPLACE_WITH_LOCAL_TELEGRAM_CHAT_ID"
  parse_mode: MarkdownV2
```

기대 결과:

- explain log와 report JSON의 `telegram_delivery_status`: `disabled`.
- 실제 전송이 필요한 경우에는 추적되지 않는 로컬 설정 파일에 token/chat id를 넣고 test
  chat으로만 실행한다.
- 실패 시 상태는 `failed:<redacted>` 형식이어야 하며 token, chat id, URL, credential
  path가 그대로 노출되면 안 된다.

## 5. 산출물 안전 스캔

실행 후 생성된 `data/` 산출물에서 현재 단계 밖 표현과 credential 패턴을 확인한다.

```bash
rg -n "추가 매수|매수 수량|목표 비중|목표비중|자동 주문|리밸런싱|주문 실행|\\bBUY\\b|\\bSELL\\b|bot_token|chat_id|spreadsheet_id|credentials_path|token_path|/Users/|REPLACE_WITH|sk-[A-Za-z0-9]" data
```

기대 결과:

- 새로 생성한 v0.2 리포트와 explain log에서는 match가 없어야 한다.
- 과거 sample report가 남아 있으면 과거 문구가 잡힐 수 있으므로, 필요한 경우 새 smoke
  전용 `data_dir`를 임시 디렉터리로 지정해 검사한다.

## 6. 사용자 실행 체크리스트

1. `git status --short`로 시작 전 변경사항을 확인한다.
2. `python3 -m pytest`를 실행한다.
3. `python3 -m src.main --settings config/settings.yaml`로 기본 smoke를 실행한다.
4. Google Sheets fixture 설정으로 한 번 더 실행한다.
5. `data/explain_logs/`에서 `macro_status`, `review_score`, `score_inputs`,
   `telegram_delivery_status`를 확인한다.
6. `data/reports/`에서 후보 목록 또는 후보 없음 사유, 리스크 경고, 생성 시각을 확인한다.
7. 산출물 안전 스캔을 실행한다.
8. 라이브 credential smoke는 별도 로컬 설정과 test chat에서만 수행한다.

## 7. 통과/실패 판정

통과:

- 테스트가 모두 통과한다.
- CLI가 exit 0으로 끝난다.
- explain log에 후보별 점수 입력값과 provider provenance가 기록된다.
- `CAUTION`은 감점/리스크로 노출되고, `RISK_OFF`는 후보를 차단한다.
- Telegram 상태가 `disabled`, `sent`, `failed:<redacted>` 중 하나로 기록된다.

실패:

- CLI가 traceback으로 종료된다.
- macro 데이터 부족이 샘플 데이터로 조용히 대체된다.
- `RISK_OFF`인데 후보가 순위에 오른다.
- 리포트가 주문 실행, 매수 수량, 목표 비중 추천을 출력한다.
- credential, sheet id, token, chat id, 로컬 경로가 산출물에 그대로 노출된다.
