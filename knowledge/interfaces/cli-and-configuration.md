---
type: interface
title: CLI and Configuration Interface
description: AutoStock의 공개 실행 인터페이스는 Python module CLI와 YAML 설정 파일이며 일부 credential 값은 환경 변수로 override된다.
resource: repo://config/settings.yaml
tags: [interface, cli, configuration]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://docs/api/API_OVERVIEW.md
    revision: WORKTREE
    kind: decision
  - source: repo://config/settings.yaml
    revision: WORKTREE
    kind: config
  - source: repo://config/settings.spreadsheet.example.yaml
    revision: WORKTREE
    kind: config
---

# Contract

공개 실행 명령은 `python3 -m src.main --settings <settings-yaml>`이다. HTTP API는 현재 없다.

`config/settings.yaml`은 sample/mock 기본 경로를 제공한다. `config/settings.spreadsheet.example.yaml`은 Google Sheets, real market data, OpenDART, cache, bounded universe smoke를 위한 예시 설정이다.

Google Sheets, OpenDART, Telegram credential은 YAML 값이 비어 있으면 환경 변수로 주입할 수 있다. 대표 환경 변수는 `AUTOSTOCK_GOOGLE_SPREADSHEET_ID`, `AUTOSTOCK_GOOGLE_CREDENTIALS_PATH`, `AUTOSTOCK_DART_API_KEY`, `AUTOSTOCK_TELEGRAM_BOT_TOKEN`, `AUTOSTOCK_TELEGRAM_CHAT_ID`다.

# Compatibility

`portfolio_source.type`은 `google_sheets` 또는 `broker_mock`를 지원한다. 알 수 없는 값은 `unsupported portfolio_source.type` 오류로 거부된다.

`market_data.mode`는 `sample`, `fixture`, `real`을 지원한다. fixture 모드는 `market_data.fixture_path`가 필요하다.
