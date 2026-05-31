# 스프레드시트 MVP 리뷰 지침

## 생명주기

이 문서는 스프레드시트 포트폴리오 분석 MVP의 리뷰 계약으로 유지한다. 런타임
문서가 아니라, 외부 리뷰 피드백을 어떤 범위와 비목표에 맞춰 판단할지 기록한다.

## 리뷰 대상

읽기 전용 Google Sheets 포트폴리오 입력, provider 기반 시장 데이터 분석, 불완전한
데이터의 보수적 처리, 후보 근거/리스크 리포팅, secret/privacy 경계를 리뷰한다.

## 제품 제약

- Google Sheets는 사용자가 관리하는 포트폴리오 원천이다.
- Google Sheets 접근은 read-only여야 한다.
- 스프레드시트 MVP에는 broker API가 필요하지 않다.
- 리포트는 주문 자동화, 수량 산정, 자동 리밸런싱 표현을 피해야 한다.
- 시장 데이터 실패, 매크로 데이터 부족, stale provider 데이터, 불완전한 재무제표는
  숨기지 않고 보수적으로 드러내야 한다.
- `macro_data_unavailable`은 후보 출력 차단이 아니라 `CAUTION` 컨텍스트와 점수 감점으로
  노출한다.
- 유효한 `RISK_OFF` 매크로 상태는 후보 출력을 전역 차단해야 한다.
- 개인 스프레드시트 데이터, sheet ID, account ID, credential 경로, token, secret-like
  값은 추적 config, warning, report, explain log에 노출되면 안 된다.

## 현재 범위 경계

v0.2는 스프레드시트 포트폴리오 분석과 live price provider fallback을 검증한다. macro
또는 fundamental source가 unavailable인 상황에서 full production-grade live candidate
generation을 보장하지 않는다. 라이브 macro/fundamental source 선정은 별도 제품/데이터
소스 결정이다.

## 리뷰 체크리스트

1. Google Sheets가 broker connector가 아니라 portfolio source로 모델링되고 readonly
   values read만 사용하는지 확인한다.
2. 스프레드시트 parser가 한국어 헤더, formatted number, percent, 빈 optional column,
   duplicate ticker aggregation을 처리하는지 확인한다.
3. real market-data provider가 sample data로 조용히 fallback하지 않는지 확인한다.
4. pykrx/FDR daily OHLCV 데이터가 `TechnicalEngine` 입력 전에 calendar-aware weekly/monthly
   technical series로 정규화되는지 확인한다.
5. missing macro, incomplete fundamentals, stale data, provider failure가 visible하고
   conservative한지 확인한다.
6. candidate output이 rationale, risks, provider provenance, review score, score inputs를
   포함하며 order automation이나 share-count sizing을 포함하지 않는지 확인한다.
7. tracked config/docs/tests에 live secret, credential path, spreadsheet ID, account ID,
   private portfolio row가 없는지 확인한다.
8. `python3 -m pytest`가 통과하는지 확인한다.

## 알려진 비목표

- 라이브 Google Sheets credential은 저장소에 포함하거나 테스트하지 않는다.
- 라이브 pykrx/FDR/Naver 네트워크 호출은 deterministic test의 필수 조건이 아니다.
- full live macro/fundamental source coverage는 별도로 계획하지 않는 한 이 MVP 범위가
  아니다.
- multi-account aggregation은 제품 기능이 아니다. 스프레드시트는 하나의 통합 포트폴리오
  입력으로 취급한다.
- 자동 주문, 수량 산정, 세금/수수료 최적화, 자동 리밸런싱은 이 MVP 밖이다.
