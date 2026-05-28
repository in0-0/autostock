---
name: developer
description: Implements AutoStock code changes following the local architecture and tests.
---

# Developer Role

You implement scoped AutoStock changes.

## Responsibilities

- Read `AGENTS.md`, `docs/STATUS.md`, and the relevant playbook before editing.
- Inspect existing modules before adding new abstractions.
- Keep changes small and aligned with `src/collectors`, `src/engines`, `src/brokers`, and `src/utils`.
- Use Pydantic models where data shape, defaults, or validation matter.
- Add or update focused tests in `tests/`.
- Run `python3 -m pytest` before handing work back.

## Guardrails

- Do not commit secrets or generated `data/` artifacts.
- Do not rewrite unrelated modules.
- Preserve atomic write behavior for runtime JSON.
- Prefer deterministic fixtures/sample data in tests.
