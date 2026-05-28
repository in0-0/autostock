# AutoStock

대한민국 주식시장(KOSPI/KOSDAQ)을 대상으로 하는 주말 배치형 AI 투자 자동화 MVP입니다.

Phase 1 목표는 매주 안정적으로 다음 산출물을 생성하는 것입니다.

- 멀티 브로커 잔고 취합
- 매크로 필터
- 재무 컷오프
- 주봉 눌림목 스크리닝
- 포트폴리오 리밸런싱 가이드
- Telegram Markdown 리포트 캐시
- explain log
- atomic write 기반 로컬 파일 보호

## 실행

```bash
python -m src.main --settings config/settings.yaml
```

현재 기본 설정은 `MockBrokerConnector`를 사용하므로 외부 증권사 API 없이도 파이프라인을 검증할 수 있습니다.

## 주요 산출물

- `data/portfolio_state.json`
- `data/explain_logs/explain_YYYY-MM-DD.json`
- `data/reports/report_YYYY-MM-DD.json`

## 다음 구현 단계

1. `src/brokers/korea_invest.py`에 한국투자증권 Open API 커넥터 구현
2. `src/brokers/kiwoom.py`에 키움증권 커넥터 구현
3. `src/collectors/market_data.py`의 샘플 데이터 공급부를 pykrx/FDR/네이버 폴백 체인으로 확장
4. `launchd` plist 추가 및 주말/일요일 스케줄 분리
