---
type: component
title: Market and Financial Data Providers
description: 시장/재무 데이터 계층은 sample, fixture, real provider를 통해 가격/거래량, 유니버스, OpenDART 재무 데이터를 수집하고 실패와 stale 상태를 보수적으로 기록한다.
resource: repo://src/collectors/market_data.py
tags: [component, market-data, opendart, cache]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://src/collectors/market_data.py
    revision: WORKTREE
    kind: code
  - source: repo://src/collectors/universe.py
    revision: WORKTREE
    kind: code
  - source: repo://src/collectors/dart.py
    revision: WORKTREE
    kind: code
  - source: repo://docs/STATUS.md
    revision: WORKTREE
    kind: decision
---

# Overview

시장 데이터는 `MarketDataBundle`로 정규화된다. sample과 fixture 모드는 deterministic 경로를 제공하고, real 모드는 pykrx, FinanceDataReader, Naver stub 순으로 provider fallback을 구성한다.

KOSPI/KOSDAQ 유니버스는 `PykrxUniverseProvider`와 `FdrUniverseProvider`가 `UniverseRecord`를 만들고, ETF/ETN/KONEX/SPAC/우선주/리츠 등 exclusion rule을 적용한다. cache가 설정되면 fresh cache를 우선하고 일부 provider 실패 시 stale grace cache를 사용할 수 있다.

OpenDART 재무 계층은 corp-code mapping과 financial statement row cache를 사용한다. API key가 없으면 각 티커에 `dart_api_key_missing` exclusion을 남기고 crash하지 않는다.

# Failure modes

Provider 실패는 telemetry와 `market_provider_failed:<provider>:<message>` warning으로 노출된다. `dart_status:013`은 raw taxonomy인 `provider_failed:opendart:dart_status:013`로 유지된다.

실제 데이터 실패를 sample 데이터로 조용히 대체하는 동작은 문서상 금지되어 있고, real provider가 모두 실패하면 provider는 `none`으로 남는다.

# Known limitations

상태 문서는 public KOSPI/KOSDAQ universe provider full-load 실패가 운영 잔여 리스크라고 기록한다. Naver provider는 last-resort stub로만 존재하며 dedicated parser 없이는 실패한다.
