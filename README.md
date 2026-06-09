# AutoStock

대한민국 주식시장(KOSPI/KOSDAQ)을 대상으로 하는 주말 배치형 후보 검토 서비스입니다.

현재 제품 방향은 읽기 전용 Google Sheets 포트폴리오를 기준으로 매주 후보 종목을 점검하고,
후보별 검토 메모를 Telegram Markdown 리포트와 로컬 JSON 아티팩트로 남기는 것입니다.

Phase 1/v0.2 기준 산출물은 다음과 같습니다.

- Google Sheets 또는 동일 파서 경로의 CSV/TSV fixture 기반 포트폴리오 입력
- 매크로 필터와 `NORMAL`/`CAUTION`/`RISK_OFF` 정책
- OpenDART 재무 컷오프와 가격/거래량 기반 주봉 눌림목 스크리닝
- 후보별 점수 입력값, 선정 근거, 리스크, provider/provenance 기록
- 후보별 구조화 검토 메모
  - 검토 이유
  - 보류/확인 사유
  - 다음 확인 항목
  - 데이터 신뢰도와 생성/출처 컨텍스트
- Telegram Markdown 리포트 캐시
- explain log와 report JSON
- atomic write 기반 로컬 파일 보호

현재 범위는 “검토 대상과 확인 메모” 제공이다. 증권사 주문, 수량 산정,
비중 추천, 운영 스케줄 변경은 별도 단계에서 다룬다.

## 실행

```bash
python -m src.main --settings config/settings.yaml
```

기본 설정은 mock/sample 경로를 사용하므로 외부 증권사 API 없이도 파이프라인을 검증할 수 있습니다.
실제 Google Sheets 입력과 Telegram 전송으로 실행할 때는
[`docs/guides/SPREADSHEET_PORTFOLIO.md`](docs/guides/SPREADSHEET_PORTFOLIO.md)를 따라
비추적 로컬 설정 파일을 만들고, `portfolio_source.type`과 `market_data.mode`를
함께 확인해야 합니다. 문서나 커밋에는 credential 값, 계좌 식별자, 개인 포트폴리오 행을 남기지 않습니다.

## 주요 산출물

- `data/portfolio_state.json`
- `data/explain_logs/explain_YYYY-MM-DD.json`
- `data/reports/report_YYYY-MM-DD.json`

`report_YYYY-MM-DD.json`에는 사람이 읽는 Markdown과 함께 후보별 `review_notes` 구조가 저장됩니다.
`explain_YYYY-MM-DD.json`의 각 후보 item에도 같은 검토 메모 컨텍스트가 포함되어, 주말 검토 이후에도
왜 후보가 올라왔고 무엇을 확인해야 하는지 추적할 수 있습니다.

## 다음 구현 단계

1. v0.2 최종 QA/리뷰 게이트를 완료하고 후보 검토 메모 산출물의 회귀 증거를 고정한다.
2. 실제 Google Sheets 테스트 시트와 Telegram 테스트 채널 검증은 credential이 준비된 뒤 P1 범위로 별도 수행한다.
3. 후보 메모의 사용자 경험을 점검해 “다음 확인” 문구와 데이터 신뢰도 표현을 개선한다.
4. 운영 스케줄, 재시도, runbook은 v0.3 운영 안정화 범위에서 다룬다.
