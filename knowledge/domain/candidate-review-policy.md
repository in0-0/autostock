---
type: domain-policy
title: Candidate Review Policy
description: v0.2 후보는 주문 지시가 아니라 재무/기술/매크로/데이터 완성도 조건을 통과한 검토 대상이며, 제외 사유는 explain log에 남긴다.
resource: repo://docs/REVIEW_INSTRUCTIONS_SPREADSHEET_MVP.md
tags: [domain, candidate-review, risk-policy]
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
  - source: repo://src/main.py
    revision: WORKTREE
    kind: code
---

# Overview

AutoStock v0.2의 후보는 종목명, 티커, 점수/순위, 선정 근거, 리스크, 데이터 출처, 구조화된 검토 메모를 포함한 확인 대상이다. 후보는 매수 주문, 수량 산정, 목표 비중 추천이 아니다.

# Invariants

재무제표와 가격/거래량 데이터가 부족한 기업은 후보에서 제외하고 stable reason taxonomy를 남긴다.

`macro_data_unavailable`은 sample 대체나 즉시 `RISK_OFF`가 아니라 `CAUTION` context와 점수 감점으로 노출된다.

유효한 `RISK_OFF` 매크로 상태는 후보 승격을 전역 차단한다.

개인 스프레드시트 데이터, sheet ID, account ID, credential 경로, token, secret-like 값은 tracked config, warning, report, explain log에 노출되면 안 된다.

# Open questions

후보군 밖 near-miss 종목을 개별 메모로 확장할지는 로드맵상 별도 제품 판단이 필요하다.
