---
type: interface
title: Runtime Artifact Contracts
description: AutoStock은 실행 결과를 `portfolio_state.json`, `explain_YYYY-MM-DD.json`, `report_YYYY-MM-DD.json` 로컬 JSON 산출물로 남긴다.
resource: repo://docs/api/API_OVERVIEW.md
tags: [interface, artifacts, json]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://README.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/api/API_OVERVIEW.md
    revision: WORKTREE
    kind: decision
  - source: repo://src/models.py
    revision: WORKTREE
    kind: code
---

# Contract

`data/portfolio_state.json`은 병합된 포트폴리오, 입력 경고, partial success 상태를 저장한다.

`data/explain_logs/explain_YYYY-MM-DD.json`은 후보별 filter 결과, rank/score, score inputs, risks, provider provenance, macro context, source warnings, exclusion counts, Telegram delivery status를 저장한다.

`data/reports/report_YYYY-MM-DD.json`은 사람이 읽는 Markdown 본문, Telegram 전송 상태, 후보별 `review_notes` 구조를 저장한다.

# Boundaries

`data/`는 생성 runtime output이다. 테스트는 generated output에 의존하지 않는다는 저장소 지침이 있다.

# Verification

`docs/guides/RUN_SERVICE_SPEC_QA.md`는 CLI smoke 후 세 산출물 존재와 `score_policy_version`, `telegram_delivery_status`, 현재 단계 밖 표현 미노출을 확인하도록 안내한다.
