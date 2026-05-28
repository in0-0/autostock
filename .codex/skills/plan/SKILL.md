---
description: "Creates AutoStock implementation plans from ROADMAP with dependencies, phases, tests, and release scope. Triggers: plan, next version, roadmap"
---

# Development Plan

## Inputs

- `docs/ROADMAP.md`
- `docs/STATUS.md`
- relevant domain docs under `docs/`
- existing code in `src/` and tests in `tests/`

## Steps

1. Identify the target version or backlog item.
2. Inspect related modules with `rg` and focused file reads.
3. Group work into independent and dependent phases.
4. For each item, name files likely to change and tests required.
5. Call out credential, provider, market-data, or portfolio-safety risk.
6. Ask for approval before starting broad or irreversible work.

## Plan Template

```markdown
## vX.Y.Z Development Plan

**Goal:** <version focus>
**Scope:** <issues or roadmap bullets>

### Target Items
| Item | Description | Dependencies | Tests |
|------|-------------|--------------|-------|
| A | ... | None | `python3 -m pytest tests/...` |

### Dependency Graph
Item A -> Item C
Item B -> Item C

### Phases
| Phase | Items | Notes |
|-------|-------|-------|
| 1 | A, B | Can be developed independently |
| 2 | C | Depends on A/B |

### Validation
- `python3 -m pytest`
- `python3 -m src.main --settings config/settings.yaml`
- artifact inspection if output behavior changed

### Risks
- Secrets:
- Partial success:
- Data freshness:
- Operational rollback:
```

## AutoStock Rules

- Keep generated artifacts out of commits.
- Prefer connector/provider boundaries over branching inside `main.py`.
- Preserve explain-log visibility when changing decisions.
