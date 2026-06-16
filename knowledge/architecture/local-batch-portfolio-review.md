---
type: system-architecture
title: Local Batch Portfolio Review System
description: AutoStock은 Google Sheets 또는 mock 입력을 읽고 KOSPI/KOSDAQ 후보를 평가해 로컬 JSON과 Telegram Markdown 리포트를 만드는 로컬 우선 Python 배치 서비스다.
resource: repo://docs/architecture/Architecture.md
tags: [architecture, batch, cli, korea-market]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://README.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/architecture/Architecture.md
    revision: WORKTREE
    kind: decision
  - source: repo://src/main.py
    revision: WORKTREE
    kind: code
---

# Overview

AutoStock의 현재 실행 단위는 `python3 -m src.main --settings config/settings.yaml`로 시작하는 단일 Python CLI 배치다. 배치는 포트폴리오 입력을 병합하고, 시장 유니버스와 가격/거래량/재무 데이터를 수집 또는 로드한 뒤, 매크로/재무/기술/포트폴리오 엔진을 순서대로 적용한다.

# Boundaries

현재 산출물은 후보 검토 목록과 확인 메모다. 저장소 문서는 증권사 주문, 매수 수량 산정, 목표 비중 추천, 자동 리밸런싱, 실증권사 API 연결을 현재 단계 밖으로 둔다.

Google Sheets는 읽기 전용 포트폴리오 원천으로 취급된다. 기존 broker/mock 경로는 로컬 회귀 테스트와 호환 기준선으로 유지된다.

# Control and data flow

1. 설정을 읽고 `portfolio_source`를 구성한다.
2. 포트폴리오 스냅샷을 내부 `PortfolioState`로 병합하고 `data/portfolio_state.json`에 저장한다.
3. real 모드에서는 KOSPI/KOSDAQ 유니버스를 provider fallback으로 해석한다.
4. 가격/거래량 provider와 OpenDART 재무 provider를 적용하고, 실패/부족 사유를 경고와 exclusion taxonomy로 남긴다.
5. `MacroEngine`, `FundamentalEngine`, `TechnicalEngine`, `PortfolioEngine`이 후보 승격과 순위를 결정한다.
6. Markdown 리포트, explain log, report JSON을 atomic write로 저장하고 Telegram 전송 상태를 기록한다.

# Known limitations

라이브 Google Sheets credential smoke와 Telegram test chat 검증은 저장소 상태 문서에서 P1 검증으로 남아 있다. 운영 스케줄, 재시도, runbook은 v0.3 범위다.
