---
description: "Packages AutoStock changes into a PR with summary, validation, risks, and release-document updates. Triggers: pr, pull request"
---

# Pull Request

## Before Opening

```bash
git status --short
python3 -m pytest
```

Confirm generated `data/` artifacts and secret files are not staged.

## PR Body Template

```markdown
## Summary
- 

## Validation
- [ ] `python3 -m pytest`
- [ ] `python3 -m src.main --settings config/settings.yaml` if runtime behavior changed

## Risk
- Broker/credential impact:
- Portfolio decision impact:
- Generated artifact impact:

## Docs
- [ ] `docs/STATUS.md` updated if project state changed
- [ ] `docs/ROADMAP.md` updated if scope changed
- [ ] `docs/HISTORY.md` reserved for release

Closes #
```

## Commit Rule

Use Conventional Commits and keep each commit scoped:

```text
feat: add korea investment broker connector
fix: block buys when market data is partial
docs: apply AutoStock development harness
```
