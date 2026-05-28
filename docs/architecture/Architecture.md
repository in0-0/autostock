# Architecture

AutoStock is a local-first Python batch pipeline. The current MVP runs from a
single CLI entrypoint and writes durable JSON artifacts for review and Telegram
delivery.

## Flow

```text
settings.yaml
  -> broker snapshots
  -> merged portfolio state
  -> macro filter
  -> fundamental cutoff
  -> technical pullback screening
  -> exit signal evaluation
  -> portfolio ranking and trade guides
  -> report + explain log + portfolio state
```

## Main Modules

| Module | Responsibility |
|--------|----------------|
| `src/main.py` | Orchestrates the full batch run |
| `src/collectors/broker_collector.py` | Loads broker connectors and merges snapshots |
| `src/collectors/market_data.py` | Supplies macro, fundamental, and technical records |
| `src/engines/macro.py` | Determines market regime |
| `src/engines/fundamental.py` | Applies financial cutoffs |
| `src/engines/technical.py` | Applies weekly pullback screening |
| `src/engines/exit.py` | Computes exit signals |
| `src/engines/portfolio.py` | Ranks candidates and creates trade guides |
| `src/reporting.py` | Renders Telegram Markdown report content |
| `src/utils/atomic.py` | Persists JSON with atomic write semantics |

## Design Constraints

- Batch runs must tolerate partial broker success.
- Persistent output must be written atomically.
- Strategy decisions should leave enough explain data to audit later.
- Provider-specific code belongs behind connector/provider boundaries.

