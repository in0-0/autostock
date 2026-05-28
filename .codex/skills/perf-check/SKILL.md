---
description: "Checks AutoStock performance and batch-runtime risks. Triggers: perf, performance"
---

# Performance Check

## Focus Areas

- Market data provider calls and fallback latency.
- Broker connector timeouts and retries.
- Avoiding repeated per-ticker network calls where batching is possible.
- JSON artifact size and serialization cost.
- Report rendering for large candidate sets.

## Steps

1. Identify changed hot paths.
2. Estimate call count by ticker and provider.
3. Check for obvious repeated work.
4. Add timing/logging only when operationally useful.
5. Recommend batching, caching, or timeout boundaries when needed.

## Report Template

```markdown
## Performance Check

| Area | Risk | Recommendation |
|------|------|----------------|

### Notes
- 
```

