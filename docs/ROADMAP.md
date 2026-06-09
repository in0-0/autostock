# 로드맵

**마지막 갱신:** 2026-06-10
**현재 기준:** Google Sheets 기반 주말 후보 검토 메모 서비스
**현재 버전:** v0.1.0 (개발 중)
**다음 버전:** v0.2.0 (주말 후보 리뷰 MVP)

## 합의된 제품 정의

AutoStock은 Google Sheets에 있는 개인 포트폴리오를 주말마다 점검하고,
KOSPI/KOSDAQ 전체 종목 중 재무제표와 가격/거래량 데이터가 충분한 기업을
정해진 기준으로 분석해 후보 검토 목록과 후보별 확인 메모를 만든 뒤 Telegram으로 알린다.

현재 단계의 후보는 종목명, 티커, 점수/순위, 선정 근거, 리스크, 데이터
출처와 검토 메모를 포함한 확인 대상이다. 증권사 주문, 수량 산정, 비중 추천,
실증권사 API 연결은 범위에서 제외한다.

## 완료된 릴리스

> 정식 릴리스 이력은 [HISTORY.md](./HISTORY.md)를 기준으로 한다. 현재 기록된
> 정식 릴리스는 없다.

## 개발 기준선

### v0.1.0 - 로컬 배치 기반선

**목표:**
- [x] 단일 Python CLI로 포트폴리오 수집, 시장 데이터 평가, 리포트 생성을 실행한다.
- [x] mock broker와 sample 데이터를 사용해 회귀 테스트 가능한 로컬 실행 경로를 제공한다.
- [x] portfolio state, explain log, Telegram Markdown report를 로컬 JSON으로 저장한다.
- [x] 핵심 Phase 1 동작을 `python3 -m pytest`로 검증한다.

**해석 변경:**
- v0.1.0의 broker/mock 경로는 로컬 회귀 테스트와 호환성 기준선이다.
- 현재 제품 방향의 중심 입력은 실증권사 API가 아니라 읽기 전용 Google Sheets다.

## 예정 릴리스

### v0.2.0 - 주말 후보 리뷰 MVP [다음]

**목표:**
- [x] Google Sheets 포트폴리오를 읽기 전용 입력 소스로 추가한다.
- [x] CSV/TSV fixture가 Google Sheets와 같은 파서 경로를 사용하도록 한다.
- [x] pykrx/FDR 가격 provider fallback, 캐시, telemetry, 주/월봉 resampling 기반을 추가한다.
- [x] 후보 리포트에서 현재 단계 밖의 주문·수량·비중 지시를 제거하고 근거/리스크/출처 중심으로 정리한다.
- [x] provider 실패와 데이터 부족을 explain log와 리포트 경고로 노출한다.
- [x] KOSPI/KOSDAQ 전체 스크리닝 유니버스를 정의하고 보유 종목 외 후보 탐색을 지원한다.
- [x] 재무제표 제공 기업을 판별할 수 있는 데이터 소스와 fallback 정책을 확정한다.
- [x] 재무제표와 가격/거래량이 부족한 기업을 후보에서 제외하고 제외 사유를 재현 가능하게 기록한다.
- [x] `NORMAL`, `CAUTION`, `RISK_OFF` 매크로 정책을 점수/순위/차단 동작에 명확히 반영한다.
- [x] 후보별 점수 또는 순위 입력값, 선정 근거, 리스크, provider provenance를 explain log에 남긴다.
- [x] 후보별 검토 이유, 보류/확인 사유, 다음 확인, 데이터 신뢰도를 구조화 메모로 남긴다.
- [x] report JSON의 `review_notes`와 explain-log item의 `review_note`에 같은 후보 메모 컨텍스트를 저장한다.
- [x] Telegram 전송 성공/실패/비활성 상태를 검증하고 실행 로그에 남긴다.
- [x] 주말 1회 실행 성공 기준을 CLI smoke, 테스트, 아티팩트 확인 로그로 고정한다.

**릴리스 게이트:**
- [x] `python3 -m pytest` 통과.
- [x] Google Sheets fixture 기반 CLI smoke run 통과.
- [x] KOSPI/KOSDAQ 유니버스와 라이브 재무제표 데이터 소스 결정.
- [x] bounded real smoke에서 pykrx 가격 provider와 FDR universe fallback 확인.
- [x] OpenDART API key 기반 bounded smoke에서 credential path와 exclusion 기록 확인.
- [x] OpenDART `dart_status:013`/재무 입력 부족 coverage 해석 보강과 raw taxonomy 회귀 테스트 고정.
- [x] OpenDART 50종목 live smoke를 기존 비추적 로컬 credential/settings, FDR/cache-backed universe, delay 조건으로 sanitized evidence 확인.
- [x] OpenDART corp-code fallback universe 3,967건 full listed-company validation 완료.
  Secret 미출력, Google Sheets/Telegram live 미실행, 0.2초 지연 호출 조건을 지켰다.
  Public KOSPI/KOSDAQ universe provider full-load 실패는 운영 잔여 리스크로 남긴다.
- [x] 데이터 부족/제외 사유가 explain log에 기록됨.
- [x] `RISK_OFF`에서 후보가 전역 차단되고, `CAUTION`에서 감점 또는 하향 표시가 검증됨.
- [x] Telegram 리포트가 후보 목록 또는 후보 없음 사유, 리스크 경고, 생성 시각을 포함함.
- [x] 리포트가 후보 검토/확인 언어를 사용하고, 현재 단계 밖의 주문·수량·비중 지시를 제공하지 않음.
- [x] 후보 검토 메모 회귀 테스트와 structured artifact 검증 통과.

### v0.3.0 - 운영 안정화

**목표:**
- [ ] 주말 실행 스케줄 템플릿을 추가한다. 운영 스케줄 변경은 별도 확인 후 진행한다.
- [ ] sample/fixture 설정과 개인 운영 설정을 더 명확히 분리한다.
- [ ] Telegram 전송 재시도와 실패 알림 정책을 강화한다.
- [ ] 주말 실행 runbook, 롤백 절차, 검증 체크리스트를 문서화한다.
- [ ] provider rate limit, stale cache, 부분 실패 기준을 운영 로그에 명확히 남긴다.

## 백로그

### 데이터 소스
- KOSPI/KOSDAQ 전체 종목 유니버스 provider bounded smoke 결과 보강: pykrx universe 경고 발생 시 FDR fallback 근거와 stale/cache 정책을 운영 문서에 연결.
- OpenDART 재무제표 provider는 구현됐으며, 로컬 YAML key 기반 bounded smoke에서
  `dart_api_key_missing` 없이 exclusion 기록을 확인했다.
  `dart_status:013`은 `provider_failed:opendart:dart_status:013` raw taxonomy로 유지하고,
  사용자 문서에서는 해당 종목/기간의 OpenDART 재무제표 미제공 또는 coverage 공백으로 해석한다.
  FDR/cache-backed 50종목 OpenDART smoke와 OpenDART corp-code fallback universe 3,967건
  full listed-company validation은 sanitized evidence로 확인했다.
  Public KOSPI/KOSDAQ universe provider full-load 실패는 provider 운영 리스크로 별도 추적한다.
- 가격/거래량 provider fallback의 stale-data 정책 강화.
- provider별 출처, 실패, 캐시 사용 여부를 explain log에 일관되게 기록.

### 전략과 리포트
- 후보군 밖 near-miss 종목을 개별 메모로 확장할지는 별도 제품 판단 후 진행한다.
- 후보 점수 산식과 순위 기준을 명확한 입력값으로 기록. 현재 `peg_macro_v1` 의미는 유지한다.
- 기존 보유 종목과 신규 후보의 중복/겹침 표시.
- 월요일 갭상승 같은 실행 시점 리스크를 후보 검토 메모의 “다음 확인” 문구로 반영.
- Telegram 메시지 길이 제한과 후보 수 제한 정책 정리.

### 현재 단계 밖
- 실증권사 API 계좌/잔고 수집.
- 증권사 주문, 수량 산정, 비중 추천.
- 호스팅 서비스화.
- 운영 스케줄 변경.

## 장기 방향

- 매주 재현 가능한 후보 리뷰를 자동 생성하는 보수적 투자 보조 도구.
- 모든 후보 선정과 제외 사유를 로컬 아티팩트로 감사할 수 있는 시스템.
- provider가 바뀌어도 제품 경계와 안전 정책이 흔들리지 않는 구조.
