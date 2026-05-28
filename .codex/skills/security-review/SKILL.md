---
description: "Reviews AutoStock for credential, portfolio data, dependency, and operational security risks. Triggers: security review, secret scan"
---

# Security Review

## Checks

```bash
git status --short
git diff --cached
rg -n "token|secret|password|chat_id|account|authorization|Bearer" .
```

Review:
- tracked settings files for live credentials
- connector auth flows
- Telegram token and chat ID handling
- generated portfolio artifacts
- logs and error messages
- dependency additions

## Severity

- P1: live credential exposure, account identifier leak, unsafe trade action
- P2: weak secret-loading pattern, overbroad logging, missing failure isolation
- P3: docs or hardening follow-up

## Output

```markdown
## Security Review

### Findings
| Severity | File | Issue | Recommendation |
|----------|------|-------|----------------|

### Secret Handling
- 

### Follow-ups
- 
```

