---
type: security-boundary
title: Secrets and Readonly Data Boundaries
description: AutoStock은 broker/Google/Telegram credential, spreadsheet ID, account identifiers, portfolio rows를 secret-like 데이터로 취급하고 Google Sheets MVP는 readonly access만 허용한다.
resource: repo://docs/guides/SECURITY.md
tags: [security, secrets, privacy, readonly]
timestamp: 2026-06-16T13:35:17Z
lifecycle: production
confidence: verified
provenance:
  - source: repo://docs/guides/SECURITY.md
    revision: WORKTREE
    kind: decision
  - source: repo://src/collectors/google_sheets.py
    revision: WORKTREE
    kind: code
  - source: repo://src/utils/redaction.py
    revision: WORKTREE
    kind: code
  - source: repo://tests/test_phase1.py
    revision: WORKTREE
    kind: test
---

# Security

보안 문서는 broker credentials, Google Sheets credentials, spreadsheet IDs, Telegram bot tokens, chat IDs, account numbers, portfolio data를 secret으로 취급한다.

Google Sheets access는 `https://www.googleapis.com/auth/spreadsheets.readonly` scope를 사용한다. MVP는 사용자 시트를 update, append, batch-update하지 않아야 한다.

실제 credential은 environment variables 또는 local-only settings 파일에 둔다. 문서, 커밋, 이슈, PR, 스크린샷에는 credential path, sheet ID, account label, private portfolio row를 남기지 않는다.

# Redaction

`sanitize_error_message`는 URL, local path, credential-like filenames, token/password/api key/sheet id/account id/chat id/client email 패턴과 긴 identifier를 redaction한다. 대표 테스트는 provider error와 Google Sheets parsing warning이 민감값을 누출하지 않는지 확인한다.

# Open questions

저장소에는 CODEOWNERS나 보안 리뷰 책임자 정보가 확인되지 않았다.
