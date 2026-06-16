---
type: component
title: Portfolio Input Sources
description: 포트폴리오 입력 계층은 Google Sheets 또는 broker mock 결과를 source-neutral snapshot으로 바꾼 뒤 티커별 통합 포지션으로 병합한다.
resource: repo://src/collectors/portfolio_source.py
tags: [component, portfolio, google-sheets]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://src/collectors/portfolio_source.py
    revision: WORKTREE
    kind: code
  - source: repo://src/collectors/google_sheets.py
    revision: WORKTREE
    kind: code
  - source: repo://tests/test_phase1.py
    revision: WORKTREE
    kind: test
---

# Overview

`PortfolioSource`는 포트폴리오 입력을 `PortfolioSourceResult`로 표준화하는 경계다. `GoogleSheetsPortfolioSource`는 live Google Sheets 또는 CSV/TSV fixture를 같은 parser 경로로 읽고, `BrokerPortfolioSource`는 기존 broker connector 출력을 같은 source result로 변환한다.

# Contract

Google Sheets 파서는 한국어 헤더 alias, `KRX:069500` 형식 티커, 쉼표가 포함된 숫자, 선택적 `평가금액`을 처리한다. 잘못된 행은 실패한 source가 아니라 `row_N:<stable_code>` warning으로 남긴다.

`merge_portfolio_sources`는 같은 티커의 여러 행을 수량 가중 평균가와 통합 시장가치로 합산한다. 계좌별 기능은 현재 제품 기능으로 문서화되어 있지 않다.

# Verification

대표 회귀 테스트는 `tests/test_phase1.py`의 Google Sheets parsing, invalid number redaction, duplicate/source merge 관련 테스트다.

# Open questions

포트폴리오 입력의 장기 기본값을 `broker_mock`에서 `google_sheets`로 전환할 시점은 릴리스 상태 문서 리뷰가 필요하다.
