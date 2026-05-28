---
description: "Turns AutoStock feature or bug requests into scoped issues and roadmap entries. Triggers: issue, backlog, feature request, bug"
---

# Issue

## Investigation

1. Reproduce or clarify the request.
2. Inspect relevant code paths.
3. Identify affected artifacts and tests.
4. Classify severity:
   - P1: unsafe recommendation, secret exposure, data loss
   - P2: incorrect result, missing provider behavior, broken workflow
   - P3: docs, cleanup, future enhancement

## Issue Template

```markdown
## Problem

## Expected Behavior

## Scope
- Code:
- Tests:
- Docs:

## Acceptance Criteria
- [ ] 

## Risk
- Broker/credential:
- Portfolio decision:
- Generated artifact:

## Roadmap Slot
vX.Y.Z
```

## Roadmap Update

Add accepted work to `docs/ROADMAP.md` under the appropriate version or backlog category.

