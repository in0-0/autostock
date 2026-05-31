# Project Status

**Last Updated:** 2026-05-31
**Status:** v0.1.0 IN DEVELOPMENT
**Current Version:** v0.1.0

## Version Plan

> Previous releases: see [HISTORY.md](./HISTORY.md)

| Version | Focus | Status |
|---------|-------|--------|
| **v0.1.0** | Phase 1 weekly batch MVP hardening | Current |
| **v0.2.0** | Spreadsheet portfolio analysis with live price fallback | Next |
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
| P2 | 4 | Live macro/fundamental sources remain future production-readiness work |
| P3+ | 0 | None recorded |

## Recent Changes

- Added spreadsheet portfolio analysis planning, provider fallback telemetry, and external review triage.
- Fixed the reviewed real-provider technical-series plan to require calendar-aware weekly/monthly resampling.

## Next Up

v0.2.0 - harden spreadsheet portfolio analysis with read-only Google Sheets input,
live price provider fallback/cache/telemetry, conservative incomplete-data gates,
and candidate rationale/risk reporting. Full live macro/fundamental source
coverage and real broker connectors remain future work.
