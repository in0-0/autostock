# 로드맵

**마지막 갱신:** 2026-06-16
**현재 기준:** v0.2.0 Google Sheets 기반 주말 후보 검토 메모 서비스
**현재 버전:** v0.2.0
**다음 버전:** v0.3.0 (운영 안정화)

## 제품 방향

AutoStock은 Google Sheets에 있는 개인 포트폴리오를 주말마다 점검하고,
KOSPI/KOSDAQ 전체 종목 중 재무제표와 가격/거래량 데이터가 충분한 기업을
정해진 기준으로 분석해 후보 검토 목록과 후보별 확인 메모를 만든 뒤 Telegram으로 알린다.

현재 단계의 후보는 종목명, 티커, 점수/순위, 선정 근거, 리스크, 데이터 출처와
검토 메모를 포함한 확인 대상이다. 증권사 주문, 수량 산정, 비중 추천,
실증권사 API 연결은 범위에서 제외한다.

## 완료된 릴리스

정식 릴리스 이력은 [HISTORY.md](./HISTORY.md)를 기준으로 한다.

- **v0.2.0** - Google Sheets 기반 주말 후보 리뷰 MVP

## 예정 릴리스

### v0.3.0 - 운영 안정화 [다음]

**목표:**
- [ ] 주말 실행 스케줄 템플릿을 추가한다. 운영 스케줄 변경은 별도 확인 후 진행한다.
- [ ] sample/fixture 설정과 개인 운영 설정을 더 명확히 분리한다.
- [ ] Telegram 전송 재시도와 실패 알림 정책을 강화한다.
- [ ] 주말 실행 runbook, 롤백 절차, 검증 체크리스트를 문서화한다.
- [ ] provider rate limit, stale cache, 부분 실패 기준을 운영 로그에 명확히 남긴다.

**초기 작업 순서:**
1. 운영 runbook과 롤백/검증 체크리스트를 먼저 문서화한다.
2. sample/fixture와 개인 운영 설정 분리 기준을 preflight 문서 또는 검사로 고정한다.
3. Telegram retry/backoff를 추가하되 실패 상태 redaction 계약을 유지한다.
4. provider rate limit, stale cache, partial failure 정보를 explain log와 운영 문서에서 같은 taxonomy로 볼 수 있게 정리한다.

## 백로그

### 데이터 소스
- KOSPI/KOSDAQ 전체 종목 유니버스 provider bounded smoke 결과 보강: pykrx universe 경고 발생 시 FDR fallback 근거와 stale/cache 정책을 운영 문서에 연결.
- 가격/거래량 provider fallback의 stale-data 정책 강화.
- provider별 출처, 실패, 캐시 사용 여부를 explain log에 일관되게 기록.

### 전략과 리포트
- 후보군 밖 near-miss 종목을 개별 메모로 확장할지는 별도 제품 판단 후 진행한다.
- 기존 보유 종목과 신규 후보의 중복/겹침 표시.
- 월요일 갭상승 같은 실행 시점 리스크를 후보 검토 메모의 “다음 확인” 문구로 반영.
- Telegram 메시지 길이 제한과 후보 수 제한 정책 정리.

### 현재 단계 밖
- 실증권사 API 계좌/잔고 수집.
- 증권사 주문, 수량 산정, 비중 추천.
- 호스팅 서비스화.
- v0.3 승인 전 운영 스케줄 변경.

## 장기 방향

- 매주 재현 가능한 후보 리뷰를 자동 생성하는 보수적 투자 보조 도구.
- 모든 후보 선정과 제외 사유를 로컬 아티팩트로 감사할 수 있는 시스템.
- provider가 바뀌어도 제품 경계와 안전 정책이 흔들리지 않는 구조.
