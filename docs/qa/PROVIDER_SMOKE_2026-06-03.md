# Provider Smoke 보고서 - v0.2 release confidence

**작성일:** 2026-06-03 KST
**범위:** P0 bounded provider smoke evidence
**결론:** 부분 통과. pykrx 가격 provider와 FDR universe fallback은 확인됐고, OpenDART는 `AUTOSTOCK_DART_API_KEY` 부재로 API 호출 전 blocker를 기록했다.

## 안전 경계

- 설정 파일은 비추적 로컬 프로필 `config/settings.provider-smoke.local`을 사용했다.
- `portfolio_source.type`은 `broker_mock`으로 유지해 Google Sheets live read를 실행하지 않았다.
- Telegram 환경 변수는 명령에서 제거했고, 설정은 placeholder/disabled 상태로 유지했다.
- `market_data.mode`는 `real`, `universe_provider.max_universe_size`는 `5`로 제한했다.
- OpenDART API key 값은 출력하지 않았고, key 부재 여부만 blocker로 기록했다.
- 생성된 `data/` 산출물과 로컬 설정 파일은 커밋 대상이 아니다.

## 실행 전 preflight

비추적 smoke 프로필에서 다음 조건을 확인했다.

| 항목 | 결과 |
|------|------|
| Google Sheets live read 미사용 | 통과 |
| Telegram placeholder 또는 disabled | 통과 |
| Telegram 환경 변수 제거 | 통과 |
| real market data mode | 통과 |
| universe size cap `<= 50` | 통과 (`5`) |
| market cache directory 설정 | 통과 |
| OpenDART key env 이름 설정 | 통과 (`AUTOSTOCK_DART_API_KEY`) |
| OpenDART key 값 존재 | 실패 아님 / blocker (`False`) |

## 실행 명령

```bash
env -u AUTOSTOCK_TELEGRAM_BOT_TOKEN \
    -u AUTOSTOCK_TELEGRAM_CHAT_ID \
    python3 -m src.main --settings config/settings.provider-smoke.local
```

## 관찰 결과

| 영역 | 결과 |
|------|------|
| CLI exit code | `0` |
| 가격 provider | `pykrx` 완료 |
| universe source | `fdr_universe` fallback, 5종목 |
| macro provider | unavailable |
| macro status | `CAUTION` |
| Telegram delivery | `disabled` |
| OpenDART status | `blocked:dart_api_key_missing` |
| 후보 제외 사유 | `dart_api_key_missing: 5` |
| explain log | `data/explain_logs/explain_2026-06-03.json` |
| report JSON | `data/reports/report_2026-06-03.json` |

## Sanitized warnings

- `universe_provider_failed:pykrx_universe:index -1 is out of bounds for axis 0 with size 0`
- `macro_data_unavailable:pykrx`
- `dart_api_key_missing`

## 판정

- **통과로 볼 수 있는 항목:** bounded real-mode 가격 provider 실행, FDR universe fallback, warning/exclusion 기록, Telegram 비활성 상태 기록, secret 미출력.
- **남은 P0 blocker:** `AUTOSTOCK_DART_API_KEY`가 없는 환경이므로 OpenDART live coverage는 아직 확인되지 않았다.
- **이번 pass의 비목표:** Google Sheets live read, Telegram live send. 두 항목은 credential이 준비된 별도 P1 smoke에서만 실행한다.

## 다음 조치

1. 비추적 로컬 환경에 `AUTOSTOCK_DART_API_KEY`가 준비되면 같은 bounded profile로 OpenDART coverage smoke를 재실행한다.
2. pykrx universe 경고가 반복되면 FDR fallback을 정상 대체 경로로 유지할지, provider별 stale/cache 정책을 강화할지 결정한다.
3. Google Sheets live read와 Telegram test chat send는 운영 credential이 아니라 테스트 전용 credential로만 별도 실행한다.
