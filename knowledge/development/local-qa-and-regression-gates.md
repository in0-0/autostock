---
type: development-workflow
title: Local QA and Regression Gates
description: AutoStock의 기본 검증은 `python3 -m pytest`, sample/mock CLI smoke, fixture smoke, artifact safety scan으로 구성된다.
resource: repo://docs/guides/RUN_SERVICE_SPEC_QA.md
tags: [development, qa, tests]
timestamp: 2026-06-16T13:35:17Z
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
---

# Verification

저장소 기본 테스트 명령은 `python3 -m pytest`다. 코드 변경 후 이 명령을 실행해야 한다는 프로젝트 지침이 있다.

서비스 스펙 QA 문서는 다음 검증을 요구한다.

* 기본 회귀 테스트.
* `python3 -m src.main --settings config/settings.yaml` sample/mock smoke.
* Google Sheets fixture와 market fixture를 사용한 smoke.
* Telegram delivery status 확인.
* `data/` 산출물에서 주문/수량/목표비중 표현과 credential pattern이 없는지 safety scan.

# Known limitations

OKF bootstrap 중에는 스킬 정책에 따라 project scripts, tests, CLI smoke를 실행하지 않았다. 이 문서는 저장소에 이미 문서화된 검증 절차를 캡처한 것이다.
