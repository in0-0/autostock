---
description: "Evaluates AutoStock architecture options for connectors, providers, scheduling, and strategy boundaries. Triggers: architect, architecture, design"
---

# Architect

## Use For

- Broker connector design.
- Market data provider fallback chains.
- Scheduling and deployment design.
- Strategy engine boundary changes.
- Secret handling and production configuration.

## Output Template

```markdown
## Architecture Decision

**Context:** 
**Decision:** 

### Options
| Option | Pros | Cons | Risk |
|--------|------|------|------|

### Recommended Plan
1. 
2. 
3. 

### Validation
- Tests:
- Smoke checks:
- Operational checks:

### Follow-ups
- 
```

## Principles

- Keep provider-specific logic behind connectors/providers.
- Keep `src/main.py` orchestration readable and thin.
- Keep strategy decisions explainable.
- Prefer local-first reliability over distributed complexity.

