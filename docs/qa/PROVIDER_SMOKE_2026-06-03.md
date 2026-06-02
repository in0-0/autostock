# Provider Smoke 보고서 - v0.2 release confidence

**작성일:** 2026-06-03 KST
**범위:** P0 bounded provider smoke evidence
**결론:** 부분 통과. pykrx 가격 provider, FDR universe fallback, OpenDART credential path를 확인했다. 초기 env-only run은 `dart_api_key_missing`을 기록했지만, 로컬 YAML key 보정 run에서는 해당 blocker가 사라지고 `dart_status:013`/재무 입력 부족 exclusion이 기록됐다.

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
| OpenDART key 값 존재 | 초기 env-only run: `False`; 로컬 YAML key 보정 run: `True` (값 미출력) |

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
| OpenDART status | 초기: `blocked:dart_api_key_missing`; 보정 run: `exercised:credential_path_no_dart_api_key_missing` |
| 후보 제외 사유 | 보정 run: `missing_peg_inputs: 4`, `missing_net_income_growth_inputs: 1`, `missing_roe_inputs: 1`, `provider_failed:opendart:dart_status:013: 1` |
| explain log | `data/explain_logs/explain_2026-06-03.json` |
| report JSON | `data/reports/report_2026-06-03.json` |

## 보정 run 메모

- 사용자가 알려준 대로 OpenDART key는 `config/settings.local.yaml`에 있었다.
- smoke profile은 원래 env var만 확인했기 때문에 초기 run에서 key를 찾지 못했다.
- 보정 run에서는 local YAML key 존재 여부만 확인하고 값을 출력하지 않은 채 ignored smoke profile에 반영했다.
- 보정 run 결과 `dart_api_key_missing`은 exclusion에서 사라졌고 OpenDART provider 결과가 재무 입력 부족 및 `dart_status:013` exclusion으로 기록됐다.

## Sanitized warnings

- `universe_provider_failed:pykrx_universe:index -1 is out of bounds for axis 0 with size 0`
- `macro_data_unavailable:pykrx`
- 초기 env-only run: `dart_api_key_missing`
- 보정 run: `provider_failed:opendart:dart_status:013`

## 판정

- **통과로 볼 수 있는 항목:** bounded real-mode 가격 provider 실행, FDR universe fallback, warning/exclusion 기록, Telegram 비활성 상태 기록, secret 미출력.
- **확인된 항목:** 로컬 YAML key 보정 run에서 OpenDART credential path가 실행됐고 `dart_api_key_missing`은 사라졌다.
- **남은 P0 follow-up:** `dart_status:013`과 재무 입력 부족 exclusion을 provider/data coverage 관점에서 해석하거나 보강해야 한다.
- **이번 pass의 비목표:** Google Sheets live read, Telegram live send. 두 항목은 credential이 준비된 별도 P1 smoke에서만 실행한다.

## 다음 조치

1. `dart_status:013`과 재무 입력 부족 exclusion을 bounded universe 표본 특성인지 provider/data coverage 문제인지 해석한다.
2. pykrx universe 경고가 반복되면 FDR fallback을 정상 대체 경로로 유지할지, provider별 stale/cache 정책을 강화할지 결정한다.
3. Google Sheets live read와 Telegram test chat send는 운영 credential이 아니라 테스트 전용 credential로만 별도 실행한다.
