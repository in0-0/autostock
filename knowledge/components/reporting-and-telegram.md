---
type: component
title: Report Rendering and Telegram Delivery
description: 리포팅 계층은 후보 근거, 리스크, source context, review note, Telegram 전송 상태를 Markdown과 JSON 산출물로 기록한다.
resource: repo://src/reporting.py
tags: [component, reporting, telegram]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://src/reporting.py
    revision: WORKTREE
    kind: code
  - source: repo://src/main.py
    revision: WORKTREE
    kind: code
  - source: repo://src/utils/telegram.py
    revision: WORKTREE
    kind: code
---

# Overview

`render_markdown_report`는 포트폴리오 요약, 매크로 상태, 후보 TOP, 시스템 리스크 경고, 후보 검토 메모, 생성 시각을 Markdown 문자열로 만든다. Telegram MarkdownV2 mode에서는 `render_telegram_markdown_v2`가 escape를 적용한다.

`_send_telegram_report`는 token/chat id가 없거나 placeholder면 `disabled`를 반환한다. 전송 성공은 `sent`, 실패는 `failed:<sanitized-message>` 형식으로 기록한다.

# Boundaries

현재 리포트는 후보 검토와 확인 언어를 사용하고, 자동 주문, 매수 수량, 목표 비중 추천을 제품 산출물로 제공하지 않는 것이 문서화된 계약이다.

# Verification

QA 문서는 report JSON과 explain log에서 `telegram_delivery_status`가 `disabled`, `sent`, `failed:<redacted>` 중 하나인지 확인하도록 요구한다.
