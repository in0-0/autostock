---
description: "Guides AutoStock test-first changes using red-green-refactor. Triggers: tdd, test first"
---

# TDD Guide

## Red

Write a focused failing test in `tests/` that captures one behavior:
- engine decision
- connector failure behavior
- settings parsing
- artifact writing
- report rendering

Run:

```bash
python3 -m pytest
```

## Green

Implement the smallest change that passes the test. Follow existing module
boundaries and Pydantic model patterns.

## Refactor

Clean up duplication only inside the touched scope. Re-run:

```bash
python3 -m pytest
```

## Good AutoStock Tests

- deterministic
- no live broker or market data calls
- no dependency on current clock unless injected/fixed
- no reliance on committed generated artifacts
