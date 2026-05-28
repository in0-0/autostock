# Project Status

**Last Updated:** 2026-05-27
**Status:** v0.1.0 IN DEVELOPMENT
**Current Version:** v0.1.0

## Version Plan

> Previous releases: see [HISTORY.md](./HISTORY.md)

| Version | Focus | Status |
|---------|-------|--------|
| **v0.1.0** | Phase 1 weekly batch MVP hardening | Current |
| **v0.2.0** | Real broker and market data connectors | Next |
| **v0.3.0** | Scheduling, alerting, and operational safety | Future |

## System Health

| Area | Status | Check |
|------|--------|-------|
| CLI pipeline | Available | `python3 -m src.main --settings config/settings.yaml` |
| Regression tests | Available | `python3 -m pytest` |
| Broker integration | Mock only | `src.brokers.mock.MockBrokerConnector` |
| Runtime output | Local JSON | `data/portfolio_state.json`, `data/reports/`, `data/explain_logs/` |

## Open Issues

| Priority | Count | Notes |
|----------|-------|-------|
| P0-P1 | 0 | None recorded |
| P2 | 4 | Next implementation items from README |
| P3+ | 0 | None recorded |

## Recent Changes

- Applied Codex-oriented document memory and workflow playbooks for AutoStock.

## Next Up

v0.2.0 - implement real broker connectors and replace sample market data with provider fallback chain.
