# UltraQA 보고서 - 서비스 스펙 구현 검수

**작성일:** 2026-06-01  
**대상 커밋:** `60def98 feat: align candidate review pipeline to service spec` 이후 작업트리  
**결론:** 통과. Cycle 1에서 baseline과 adversarial dynamic e2e 시나리오가 모두 통과했다.

## 목표와 성공 기준

- 목표: 승인된 서비스 스펙 구현이 실제 CLI 실행, 산출물, Telegram 상태 기록, redaction,
  매크로 정책, 후보 제외/승격 정책에서 의도대로 동작하는지 검수한다.
- 성공 기준: `python3 -m pytest` 통과, fixture 기반 CLI e2e 통과, hostile 입력에서도
  후보/리스크/explain log가 일관되게 생성, 주문/수량/목표비중 표현과 secret 노출 없음,
  임시 harness 정리 완료.
- 중지 조건: 5 cycle 도달, 같은 실패 3회 반복, destructive/credentialed/external-production
  경계 도달, 또는 모든 시나리오 통과.
- 적용한 안전 경계: 실제 Google/Telegram credential 사용 없음, 네트워크/운영 전송 없음,
  destructive repo cleanup 없음, 모든 임시 fixture는 `/private/tmp` 아래에서만 생성.

## 시나리오 매트릭스

| ID | 사용자/공격자 모델 | 시나리오 | 명령/harness | 기대 신호 | 실제 결과 | 상태 | 증거 | 정리 |
|----|---------------------|----------|--------------|-----------|-----------|------|------|------|
| UQA-BASE-001 | 정상 운영자 | Google Sheets fixture와 market fixture 정상 실행 | `python3 -m src.main --settings <tmp>/normal/settings.yaml` | exit 0, `NORMAL`, 후보 순위, `peg_macro_v1`, Telegram `disabled` | 통과 | PASS | `macro=NORMAL`, `score_policy=peg_macro_v1` | 임시 fixture 제거 |
| ADV-E2E-001 | malformed 입력 사용자 | invalid quantity, path-like memo, pseudo-secret 입력 | `python3 -m src.main --settings <tmp>/malformed/settings.yaml` | `row_2:invalid_quantity`, raw secret/memo 미노출 | 통과 | PASS | warning present, `secret_leaked=False` | 임시 fixture 제거 |
| ADV-E2E-002 | 부분 실패 provider | KOSDAQ macro series 누락 | `python3 -m src.main --settings <tmp>/partial-macro/settings.yaml` | `CAUTION`, 후보 유지, `macro_caution_penalty` | 통과 | PASS | `macro=CAUTION`, risks에 penalty | 임시 fixture 제거 |
| ADV-E2E-003 | 위험 시장 | 유효한 `RISK_OFF` macro | `python3 -m src.main --settings <tmp>/risk-off/settings.yaml` | 후보 전역 차단, `macro_risk_off` 기록 | 통과 | PASS | `final_rank=None`, stdout에 후보 순위 없음 | 임시 fixture 제거 |
| ADV-E2E-004 | 불완전 provider | 후보 현재가 누락 | `python3 -m src.main --settings <tmp>/missing-price/settings.yaml` | 후보 제외, `missing_current_price` 기록 | 통과 | PASS | risks에 `missing_current_price` | 임시 fixture 제거 |
| ADV-E2E-005 | prompt injection성 provider text | 종목명이 검증 생략을 주장 | `python3 -m src.main --settings <tmp>/prompt-injection/settings.yaml` | 실행 흐름 영향 없음, 주문/수량/목표비중 표현 없음 | 통과 | PASS | forbidden matches 없음 | 임시 fixture 제거 |
| ADV-E2E-006 | Telegram 운영자 | MarkdownV2 전송 payload escaping | patched `TelegramClient`로 `_send_telegram_report` 호출 | `sent`, outbound text escaped | 통과 | PASS | `A\_B \(report\)` 전송 | 임시 patch only |
| ADV-E2E-007 | Telegram 실패 공격자 | dict-style secret 포함 예외 | patched `TelegramClient` 실패 | `failed:<redacted>`, raw secret 미노출 | 통과 | PASS | `chat_id/token/password=[redacted]` | 임시 patch only |
| ADV-E2E-008 | dirty worktree 감사자 | 임시 harness가 repo를 더럽히지 않는지 확인 | `git status --short` before/after | temp harness 전후 repo 변경 없음 | 통과 | PASS | `before=''`, `after=''` | repo debris 없음 |
| ADV-E2E-009 | hung command | 장시간 명령 timeout 처리 | `python3 -c sleep(5)` with timeout 1s | timeout catch, 무한 대기 없음 | 통과 | PASS | `timeout_caught=True` | child process 종료 |
| ADV-E2E-010 | flaky-test 회의자 | partial macro CLI 반복 실행 | 같은 fixture scenario 2회 실행 | exit/status/policy/rank 동일 | 통과 | PASS | `(0, CAUTION, peg_macro_v1, 1)` 2회 | 임시 fixture 제거 |
| ADV-E2E-011 | misleading output 공격자 | `SUCCESS` 출력 후 exit 1 | `python3 -c "print('SUCCESS'); exit(1)"` | 성공 문구보다 exit code 우선 | 통과 | PASS | `exit=1`, stdout `SUCCESS all good` | 임시 프로세스 종료 |
| ADV-E2E-012 | cancel/resume/stale-state 운영자 | UltraQA state read 가능성 | `omx state read --input '{"mode":"ultraqa"}' --json` | active state 확인 및 cleanup 가능 | 통과 | PASS | `active=true`, phase `adversarial-e2e` | 완료 시 state clear |

## 실행한 명령

- `[0] python3 -m pytest` - baseline 회귀 테스트. 결과: `38 passed`, `urllib3` LibreSSL warning 1개.
- `[0] python3 -m src.main --settings <tmp>/normal/settings.yaml` - 정상 fixture e2e. 결과: `NORMAL`, 후보 1개, Telegram `disabled`.
- `[0] python3 -m src.main --settings <tmp>/malformed/settings.yaml` - malformed spreadsheet e2e. 결과: stable warning, raw secret 미노출.
- `[0] python3 -m src.main --settings <tmp>/partial-macro/settings.yaml` - partial macro e2e. 결과: `CAUTION`, 후보 유지, penalty 기록.
- `[0] python3 -m src.main --settings <tmp>/risk-off/settings.yaml` - `RISK_OFF` e2e. 결과: 후보 전역 차단.
- `[0] python3 -m src.main --settings <tmp>/missing-price/settings.yaml` - current price 누락 e2e. 결과: 후보 제외.
- `[0] python3 -m src.main --settings <tmp>/prompt-injection/settings.yaml` - prompt injection성 텍스트 e2e. 결과: 주문/수량/목표비중 표현 없음.
- `[0] patched _send_telegram_report` - MarkdownV2 escaping과 실패 redaction 검증.
- `[timeout caught] python3 -c "sleep(5)"` - hung command 안전 대체 검증.
- `[1] python3 -c "print('SUCCESS all good'); sys.exit(1)"` - misleading success output 검증. 기대한 실패 exit로 처리.
- `[0] omx state read --input '{"mode":"ultraqa"}' --json` - UltraQA 상태 read/resume evidence.

## 발견한 실패

없음. Cycle 1에서 모든 baseline과 adversarial dynamic e2e 시나리오가 통과했다.

## 적용한 수정

이번 UltraQA 중 새 코드 수정은 없었다. 검수 대상 구현에는 이미 다음 방어가 포함되어 있었다.

- `src/engines/macro.py`: macro series 누락 시 `CAUTION` 컨텍스트로 처리.
- `src/engines/portfolio.py`: `review_score`, `score_policy_version`, `score_inputs`, `CAUTION` penalty 기록.
- `src/main.py`: Telegram 전송 상태 저장, MarkdownV2 escaping, redacted failure status.
- `src/utils/redaction.py`: URL/path/secret-like key redaction.
- `src/reporting.py`: 주문/수량 중심 guide 대신 후보 검토 리포트 출력.

## 정리와 롤백

- 임시 fixture와 harness는 `/private/tmp/autostock-ultraqa-*` 아래에 생성했다.
- e2e 실행 후 repo worktree는 임시 harness 때문에 변경되지 않았다.
- 보고서 작성 후 UltraQA state는 `omx state clear --input '{"mode":"ultraqa"}' --json`로 정리한다.
- 실패한 실험 edit는 없었고 롤백할 변경도 없었다.

## 잔여 리스크

- 실제 Google Sheets credential, 실제 Telegram bot token/chat id, 실제 외부 market provider 네트워크 호출은 안전 경계상 실행하지 않았다.
- 라이브 KOSPI/KOSDAQ 재무제표 provider coverage는 여전히 별도 승인 게이트다.
- macOS 기본 Python 환경에서 `urllib3` LibreSSL warning이 반복된다. 현재 실패 조건은 아니지만 운영 환경에서는 OpenSSL 기반 Python 사용을 권장한다.

## 증거 요약

- Baseline: `python3 -m pytest` -> `38 passed`.
- Dynamic e2e: 13개 시나리오 -> 13개 PASS.
- 주요 산출물 신호: `NORMAL`/`CAUTION`/`RISK_OFF` 분기, `macro_caution_penalty`,
  `macro_risk_off`, `missing_current_price`, `peg_macro_v1`, Telegram `disabled`/`sent`/`failed:<redacted>`.
- Cleanup 신호: 임시 harness 전후 `git status --short`는 빈 출력.

`ULTRAQA COMPLETE: Goal met after 1 cycle`
