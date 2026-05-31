# Roadmap

**Last Updated:** 2026-05-31
**Current Version:** v0.1.0 (In Development)
**Next Version:** v0.2.0 (Spreadsheet Portfolio Analysis)

## Completed Releases

> Release history: see [HISTORY.md](./HISTORY.md)

## Upcoming Releases

### v0.1.0 - Phase 1 Weekly Batch MVP

**Goals:**
- [x] Merge multi-broker snapshots through a mock connector.
- [x] Evaluate macro, fundamental, technical, exit, and portfolio engines.
- [x] Cache portfolio state, explain logs, and Telegram Markdown reports with atomic writes.
- [x] Cover key Phase 1 behavior with regression tests.

### v0.2.0 - Spreadsheet Portfolio Analysis [Next]

**Goals:**
- [x] Add read-only Google Sheets portfolio ingestion through a source-neutral portfolio boundary.
- [x] Extend `src/collectors/market_data.py` with pykrx/FDR live price provider fallback, cache/telemetry, calendar-aware weekly/monthly technical series, and an explicit Naver last-resort stub.
- [x] Add provider failure handling and explain-log visibility for partial market data.
- [x] Report buy candidates with rationale and risk notes, without order sizing or automatic rebalancing.
- [ ] Keep full live macro/fundamental source coverage out of v0.2 unless a separate data-source decision is made; unavailable macro and incomplete fundamentals must remain conservative blockers.

**Release Gate:**
- [ ] Complete the final Ultragoal code-review/verifier checkpoints before tagging v0.2.0.

### v0.3.0 - Operations and Delivery

**Goals:**
- [ ] Add launchd plist templates for weekend and Sunday schedules.
- [ ] Separate local sample settings from production credential settings.
- [ ] Add Telegram delivery verification and retry behavior.
- [ ] Add operational runbook for weekly review and rollback.

## Backlog

### Broker Connectors
- Korea Investment Open API account balance and holdings collection.
- Kiwoom balance and holdings collection.
- Credential loading pattern that keeps secrets outside tracked files.

### Market Data
- Provider fallback chain: pykrx -> FinanceDataReader -> Naver parser implementation.
- Clear stale-data policy for weekly screening.
- Provider-level telemetry in explain logs.
- Live macro and fundamental data-source selection for production-grade live candidate generation.

### Strategy
- Monday gap-up cap verification against weekly candidates.
- Exit signal expansion beyond the initial MVP.
- Portfolio sizing behavior for low-candidate environments.
- Portfolio concentration, target-weight-gap, and existing-holding overlap filters after the spreadsheet MVP.

## Long-term Vision

- Reliable weekend automation that produces auditable investment guidance without manual spreadsheet work.
- Provider-agnostic broker and market data collection with graceful partial success.
- Transparent recommendations where every filter and final action is explainable from local artifacts.
