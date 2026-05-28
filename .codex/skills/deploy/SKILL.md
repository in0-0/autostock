---
description: "Deploys or schedules AutoStock batch runs with pre-checks, health checks, and rollback notes. Triggers: deploy, schedule, launchd"
---

# Deploy

AutoStock deployment currently means configuring the local scheduled batch run.

## Pre-checks

```bash
python3 -m pytest
python3 -m src.main --settings config/settings.yaml
```

Confirm:
- settings path is correct
- credentials are available outside source control
- generated artifacts land under `data/`
- Telegram delivery is either disabled or verified in the target environment

## launchd Plan

For macOS scheduling, create plist files only after confirming:
- weekday/weekend run schedule
- Python executable path
- project path
- log path
- settings path

## Rollback

- Disable the launchd job.
- Revert to the previous settings file.
- Keep the latest generated report and explain log for audit.
