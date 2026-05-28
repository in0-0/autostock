---
description: "Processes PR review feedback and routes fixes through focused implementation and QA. Triggers: review, address feedback"
---

# Review Feedback

## Steps

1. Read all unresolved comments and requested changes.
2. Classify each item:
   - P1: correctness, safety, secrets, data loss
   - P2: missing tests, maintainability, edge cases
   - P3: style or follow-up
3. Implement only accepted fixes.
4. Re-run the smallest meaningful validation, then `python3 -m pytest`.
5. Summarize what changed and what remains.

## AutoStock Review Checklist

- Does partial broker or market-data success behave safely?
- Are explain logs still complete enough to audit the decision?
- Are generated artifacts ignored?
- Are credentials and account identifiers protected?
- Are tests deterministic and independent of live providers?
