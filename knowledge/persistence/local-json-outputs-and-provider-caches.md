---
type: persistence
title: Local JSON Outputs and Provider Caches
description: AutoStock은 로컬 JSON 산출물과 provider cache를 atomic write로 저장하고 schema version과 freshness를 확인해 재사용한다.
resource: repo://src/utils/atomic.py
tags: [persistence, json, cache]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://src/utils/atomic.py
    revision: WORKTREE
    kind: code
  - source: repo://src/collectors/market_data.py
    revision: WORKTREE
    kind: code
  - source: repo://src/collectors/universe.py
    revision: WORKTREE
    kind: code
  - source: repo://src/collectors/dart.py
    revision: WORKTREE
    kind: code
---

# State and consistency

`atomic_write_json`은 대상 디렉터리에 임시 파일을 쓰고 flush/fsync 후 `os.replace`로 교체한다. 예외가 발생하면 남은 임시 파일을 제거한다.

Market data cache는 `MARKET_DATA_CACHE_SCHEMA_VERSION = 2`를 요구하고, macro payload와 `macro_provider`가 없으면 무효로 본다. Universe cache는 `UNIVERSE_CACHE_SCHEMA_VERSION = 1`을 요구한다. OpenDART corp-code와 financial statement cache도 각각 schema version을 가진다.

# Freshness

설정에는 가격 cache max age, price freshness, weekly technical freshness, fundamental freshness가 분리되어 있다. OpenDART financial cache는 기본 120일 fresh window와 180일 stale grace를 코드에 둔다.

# Security

Generated portfolio/report/explain artifacts와 credential이 포함될 수 있는 local settings는 source control에 포함하지 않는 것이 보안 문서의 규칙이다.
