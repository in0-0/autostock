---
type: operations
title: Weekend Batch Operation Scope
description: AutoStock은 현재 로컬 주말 배치 실행을 기준으로 하며 스케줄, 재시도, runbook 강화는 v0.3 계획 범위다.
resource: repo://docs/STATUS.md
tags: [operations, schedule, runbook]
timestamp: 2026-06-16T14:00:00Z
lifecycle: proposed
confidence: verified
provenance:
  - source: repo://docs/ROADMAP.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/STATUS.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/guides/RUN_SERVICE_SPEC_QA.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/qa/V0_2_RELEASE_CANDIDATE_QA_2026-06-16.md
    revision: WORKTREE
    kind: decision
---

# Overview

현재 운영 기준은 사용자가 로컬 설정과 credential을 준비한 뒤 CLI를 실행하고, 산출물과 Telegram 상태를 확인하는 방식이다. 실제 Google Sheets 읽기와 Telegram test chat 발송은 credential 준비 후 별도 검증으로 남아 있다.

# Proposed scope

로드맵의 v0.3 목표는 주말 실행 스케줄 템플릿, sample/fixture 설정과 개인 운영 설정 분리, Telegram 전송 재시도와 실패 알림, runbook/롤백/검증 체크리스트, provider rate limit/stale cache/부분 실패 로그 강화다.

초기 작업 순서는 운영 runbook과 롤백/검증 체크리스트 문서화, sample/fixture와 개인 운영 설정 분리 기준 고정, Telegram retry/backoff 추가, provider rate limit/stale cache/partial failure taxonomy 정리 순서다.

# Failure modes

Public KOSPI/KOSDAQ universe provider full-load 실패는 현재 운영 잔여 리스크로 문서화되어 있다. 전체 유니버스 실행은 cache와 request delay 없이 수행하지 않는 것이 가이드에 명시되어 있다.
