# Spreadsheet MVP Review Instructions

## Lifecycle

This document is retained as the review contract for the spreadsheet portfolio
analysis MVP. It is not runtime documentation; it records the review scope and
non-goals that external review feedback should be judged against.

## Review Target

Review the spreadsheet MVP implementation for read-only Google Sheets portfolio
ingestion, provider-backed market-data analysis, conservative incomplete-data
handling, candidate rationale/risk reporting, and secret/privacy boundaries.

## Product Constraints

- Google Sheets is the user-maintained portfolio source of truth.
- Google Sheets access must be read-only.
- Broker APIs are not required for the spreadsheet MVP.
- Reports must avoid automated order, share-count sizing, and rebalancing
  language.
- Market-data failures, missing macro data, stale provider data, and incomplete
  fundamentals must be visible and conservative.
- `macro_data_unavailable` and valid `RISK_OFF` macro states must block candidate
  output.
- Private spreadsheet data, sheet IDs, account IDs, credential paths, tokens,
  and secret-like values must not leak into tracked config, warnings, reports,
  or explain logs.

## Current Scope Boundary

v0.2 validates spreadsheet portfolio analysis and live price provider fallback.
It does not guarantee full production-grade live candidate generation when macro
or fundamental sources are unavailable. Live macro/fundamental source selection
is a future product/data-source decision.

## Review Checklist

1. Confirm Google Sheets is modeled as a portfolio source, not a broker
   connector, and uses readonly values reads only.
2. Confirm spreadsheet parsing accepts Korean headers, formatted numbers,
   percentages, blank optional columns, and duplicate ticker aggregation.
3. Confirm real market-data providers do not silently fall back to sample data.
4. Confirm Pykrx/FDR daily OHLCV data is normalized into calendar-aware weekly
   and monthly technical series before `TechnicalEngine` consumes it.
5. Confirm missing macro, incomplete fundamentals, stale data, and provider
   failures are visible and conservative.
6. Confirm candidate output includes rationale, risks, and provider provenance
   without order automation or share-count sizing.
7. Confirm tracked config/docs/tests do not contain live secrets, credential
   paths, spreadsheet IDs, account IDs, or private portfolio rows.
8. Confirm `python3 -m pytest` passes.

## Known Non-Goals

- Live Google Sheets credentials are not included or tested in the repository.
- Live pykrx/FDR/Naver network calls are not required for deterministic tests.
- Full live macro/fundamental source coverage is not part of this MVP unless
  separately planned.
- Multi-account aggregation is not a product feature. The spreadsheet is treated
  as one consolidated portfolio input.
- Automated orders, share-count sizing, tax/fee optimization, and automatic
  rebalancing are outside this MVP.
