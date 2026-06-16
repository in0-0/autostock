---
type: component
title: Candidate Evaluation Engines
description: 후보 평가 엔진은 매크로 상태, 재무 컷오프, 기술적 눌림목, PEG 기반 점수를 조합해 검토 후보와 exclusion context를 만든다.
resource: repo://src/engines/portfolio.py
tags: [component, strategy, scoring]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://src/engines/macro.py
    revision: WORKTREE
    kind: code
  - source: repo://src/engines/fundamental.py
    revision: WORKTREE
    kind: code
  - source: repo://src/engines/technical.py
    revision: WORKTREE
    kind: code
  - source: repo://src/engines/portfolio.py
    revision: WORKTREE
    kind: code
---

# Overview

`MacroEngine`은 KOSPI/KOSDAQ 월봉 10MA 조건과 데이터 완성도를 기준으로 `NORMAL`, `CAUTION`, `RISK_OFF`를 만든다. `FundamentalEngine`은 ROE, 부채비율, 업종별 영업이익률, 턴어라운드, 성장률 괴리 조건을 평가한다. `TechnicalEngine`은 월봉 상승 추세, 상장 기간, 주봉 20/60MA 눌림목, 거래량 감소 조건을 평가한다.

`PortfolioEngine.rank_candidates`는 최소 후보 수를 만족할 때 `peg_macro_v1` 점수 입력값을 기록하고 PEG가 낮은 후보를 우선 순위화한다. `CAUTION`은 0.85 macro penalty와 `macro_caution_penalty` risk를 추가한다.

# Invariants

`RISK_OFF`는 `src/main.py`에서 rankable candidate를 비우고 각 후보에 `macro_risk_off` exclusion을 추가하는 전역 차단 정책이다.

후보가 리포트에 오르려면 재무/기술 조건뿐 아니라 현재가, 충분한 weekly/monthly series, PEG, provider provenance, source risk policy를 통과해야 한다.

# Known limitations

`PortfolioEngine.build_trade_guides`는 남아 있지만 문서상 v0.2 주 실행 경로에서는 주문/수량/비중 추천을 출력하지 않는다.
