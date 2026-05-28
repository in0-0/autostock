---
name: cli-scenario-tester
description: Tester role for AutoStock CLI scenarios; AutoStock currently has no browser UI.
---

# CLI Scenario Tester Role

AutoStock currently has no browser UI. For this project, browser testing is
usually skipped and replaced with CLI scenario verification:

```bash
python3 -m src.main --settings config/settings.yaml
python3 -m pytest
```

If a web dashboard is added later, update this role with real browser scenarios.
