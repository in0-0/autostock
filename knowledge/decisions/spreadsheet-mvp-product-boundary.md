---
type: decision
title: Spreadsheet MVP Product Boundary
description: v0.2는 Google Sheets 기반 후보 검토 MVP이며 주문, 수량 산정, 목표 비중 추천, 실증권사 API 연결은 범위 밖으로 둔다.
resource: repo://docs/ROADMAP.md
tags: [decision, product-boundary, v0.2]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://README.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/ROADMAP.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/REVIEW_INSTRUCTIONS_SPREADSHEET_MVP.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/architecture/Architecture.md
    revision: WORKTREE
    kind: decision
---

# Decision

AutoStock v0.2의 중심 입력은 실증권사 API가 아니라 사용자가 관리하는 Google Sheets 포트폴리오다. 서비스는 시트를 읽고 후보 검토 목록과 검토 메모를 만들며, Telegram Markdown 리포트와 로컬 JSON 아티팩트로 남긴다.

# Consequences

Broker/mock 경로는 로컬 회귀 테스트와 호환 기준선으로 유지된다.

리포트와 산출물은 후보 검토, 확인 항목, 데이터 신뢰도, provider provenance를 강조한다. 주문 자동화, 매수 수량, 목표 비중 추천, 자동 리밸런싱 표현은 현재 단계 밖이다.

실제 Google Sheets credential과 Telegram live send 검증은 저장소에 credential을 남기지 않는 별도 로컬 smoke로 수행해야 한다.

# Open questions

정식 v0.2 릴리스 시점과 릴리스 태그는 `docs/HISTORY.md`에 아직 기록되어 있지 않다.
