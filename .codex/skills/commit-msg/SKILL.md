---
description: "Generates Conventional Commit messages for AutoStock changes. Triggers: commit message, commit-msg"
---

# Commit Message

## Format

```text
<type>: <short imperative summary>

<optional body>
```

Allowed types:
- `feat`
- `fix`
- `docs`
- `test`
- `refactor`
- `chore`

## Examples

```text
docs: apply AutoStock development harness
feat: add korea investment broker connector
fix: block buys on partial market data
test: cover technical pullback rejection path
```

## Checklist

- Summary is under 72 characters when possible.
- Scope is one coherent change.
- Body explains why when behavior or risk changed.

