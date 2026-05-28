---
description: "Reports AutoStock document, git, test, and runtime status. Triggers: status, health"
---

# Status

## Checks

```bash
cat docs/STATUS.md
cat docs/ROADMAP.md
cat docs/HISTORY.md
git status --short
python3 -m pytest
```

Optional smoke run:

```bash
python3 -m src.main --settings config/settings.yaml
```

## Report Template

```markdown
## Current Status

**Version:** vX.Y.Z
**Branch:** <branch>

### Health
| Area | Status | Notes |
|------|--------|-------|
| Tests | PASS/FAIL | `python3 -m pytest` |
| CLI | PASS/FAIL/SKIPPED | batch smoke run |
| Git | CLEAN/DIRTY | important changed files |
| Docs | CURRENT/STALE | STATUS/ROADMAP/HISTORY |

### Next Milestone
<from ROADMAP>
```
