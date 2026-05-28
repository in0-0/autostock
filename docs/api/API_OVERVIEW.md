# API Overview

AutoStock currently has no HTTP API. Its public interface is the Python CLI and
the connector contracts under `src/brokers/`.

## CLI

```bash
python3 -m src.main --settings config/settings.yaml
```

## Broker Connector Contract

Broker connectors implement the base interface in `src/brokers/base.py` and are
loaded from dotted paths in `config/settings.yaml`.

Expected output:
- account and cash/deposit snapshot
- current holdings with ticker, name, quantity, and current price
- connector failure information when partial success occurs

## Runtime Artifacts

| Artifact | Purpose |
|----------|---------|
| `data/portfolio_state.json` | Latest merged portfolio state |
| `data/explain_logs/explain_YYYY-MM-DD.json` | Filter-by-filter audit trail |
| `data/reports/report_YYYY-MM-DD.json` | Generated Telegram Markdown report |
