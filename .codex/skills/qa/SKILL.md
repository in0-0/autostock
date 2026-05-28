---
description: "Runs AutoStock QA: tests, CLI smoke run, generated artifact checks, and review summary. Triggers: qa, test, quality check"
---

# QA

## Default Checks

Run from project root:

```bash
python3 -m pytest
python3 -m src.main --settings config/settings.yaml
git status --short
```

If runtime behavior changed, inspect generated artifacts without committing them:

```bash
ls data
ls data/explain_logs
ls data/reports
```

## Optional Review

When available:

```bash
codex review --uncommitted
```

## Report Template

```markdown
## QA Report

**Scope:** <change summary>
**Date:** YYYY-MM-DD HH:MM

| Area | Result | Details |
|------|--------|---------|
| Unit tests | PASS/FAIL | `python3 -m pytest` |
| CLI smoke | PASS/FAIL/SKIPPED | `python3 -m src.main --settings config/settings.yaml` |
| Artifacts | PASS/FAIL/SKIPPED | portfolio/report/explain output |
| Review | PASS/WARN/SKIPPED | Codex or manual review |

### Findings
- P1:
- P2:
- P3:

### Next Actions
1. ...
```

## Failure Handling

- Test failures block `/pr` and `/release`.
- CLI failures caused by missing real credentials should be marked as environment-blocked, not ignored.
- Any secret exposure found during QA is P1.
