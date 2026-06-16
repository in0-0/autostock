---
type: development-workflow
title: Local QA and Regression Gates
description: AutoStock의 기본 검증은 `python3 -m pytest`, sample/mock CLI smoke, fixture smoke, artifact safety scan으로 구성된다.
resource: repo://docs/guides/RUN_SERVICE_SPEC_QA.md
tags: [development, qa, tests]
timestamp: 2026-06-16T14:10:00Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://AGENTS.md
    revision: WORKTREE
    kind: decision
  - source: repo://docs/guides/RUN_SERVICE_SPEC_QA.md
    revision: WORKTREE
    kind: decision
  - source: repo://tests/test_phase1.py
    revision: WORKTREE
    kind: test
  - source: repo://docs/qa/V0_2_RELEASE_CANDIDATE_QA_2026-06-16.md
    revision: WORKTREE
    kind: decision
---

# Verification

저장소 기본 테스트 명령은 `python3 -m pytest`다. 코드 변경 후 이 명령을 실행해야 한다는 프로젝트 지침이 있다.

서비스 스펙 QA 문서는 다음 검증을 요구한다.

* 기본 회귀 테스트.
* `python3 -m src.main --settings config/settings.yaml` sample/mock smoke.
* Google Sheets fixture와 market fixture를 사용한 smoke.
* Telegram delivery status 확인.
* `data/` 산출물에서 주문/수량/목표비중 표현과 credential pattern이 없는지 safety scan.

2026-06-16 KST v0.2.0 릴리즈 QA에서는 `python3 -m pytest` 79개 테스트, sample/mock CLI smoke, runtime artifact 구조 확인, `data/` 안전 스캔이 통과했다. 실제 Google Sheets live read와 Telegram test chat send는 credential이 필요한 P1 운영 smoke로 남아 있다.

# Known limitations

Live credential smoke는 저장소에 credential을 남기지 않는 로컬 설정과 test sheet/test chat이 있을 때만 수행한다.
