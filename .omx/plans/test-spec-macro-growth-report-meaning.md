# Test Spec: Meaningful Macro and Growth-Candidate Report

## Scope
Regression tests for report rendering and diagnostic classification derived from `.omx/plans/prd-macro-growth-report-meaning.md`.

## Test Cases

### T1. Unavailable macro renders interpreted Korean text
- Arrange: `macro_status=MacroStatus.CAUTION`, `macro_indicators` with `macro_data_unavailable=True`, `kospi_above_10ma=False`, `kosdaq_above_10ma=False`, `us_rate=None`, `yield_curve_10y2y=None`.
- Act: call `render_markdown_report`.
- Assert:
  - Does not contain `KOSPI 10MA: False`.
  - Does not contain `KOSDAQ 10MA: False`.
  - Does not contain `미국 기준금리: None`.
  - Does not contain `장단기 금리차: None`.
  - Contains Korean unavailable/limited-judgment wording.

### T2. Empty candidate output translates exclusion reasons
- Arrange: no ranked candidates, candidate exclusion counts containing `missing_peg_inputs`, `missing_net_income_growth_inputs`, `missing_roe_inputs`, `missing_debt_ratio_inputs`, `provider_failed:opendart:dart_status:013`.
- Act: render report.
- Assert:
  - Raw keys are absent from normal user-facing report lines.
  - Korean labels mention valuation/PEG input gap, net-income growth input gap, ROE input gap, debt-ratio input gap, and OpenDART/report-provider failure.
  - Report explains no actionable candidates are available because required review data is incomplete.
  - Prefer table-driven coverage for the mapping so all named reasons are checked without brittle one-off assertions.

### T3. Verification tasks are deterministic, prioritized, deduplicated, and capped
- Arrange: macro warning, OpenDART failure, multiple missing input counts, stale/short price warnings, and portfolio source warnings, including duplicate reasons in the same source category.
- Act: render report.
- Assert:
  - A `검증 필요` section exists.
  - Tasks are deduplicated by source category before capping.
  - It contains no more than 3 task bullets after deduplication.
  - Macro/provider/fundamental blockers are prioritized above lower-impact row hygiene when all are present.
  - Output ordering is stable for repeated calls with the same inputs.

### T4. System status is separated from user-actionable checks
- Arrange: warnings plus `telegram_delivery_status="sent"`.
- Act: render report.
- Assert:
  - Telegram status appears in an `운영 상태` or equivalent system/operational status section.
  - The `검증 필요` section does not contain Telegram delivery status or other purely operational status lines.

### T5. Existing ranked candidate rendering remains intact
- Arrange: one ranked candidate with score/rationale/risks/provider.
- Act: render report.
- Assert:
  - Candidate rank, name, ticker, PEG, score, strategy type, rationale/risks/provider are present.
  - New diagnostics do not remove normal candidate output.

### T6. Unknown reason fallback is safe
- Arrange: exclusion count with an unknown reason key.
- Act: render report.
- Assert:
  - Report shows a Korean fallback such as 기타 데이터 확인 필요.
  - Normal user-facing report lines do not leak the unknown raw key.
  - No exception is raised.

### T7. Macro risk-off empty candidate explanation
- Arrange: `macro_status=MacroStatus.RISK_OFF`, no ranked candidates, and minimal or no provider/input exclusions.
- Act: render report.
- Assert:
  - Empty candidate explanation mentions macro/risk-off blocking or market-risk context.
  - It does not incorrectly attribute the empty state only to provider/input data gaps.

### T8. Realistic degraded report regression
- Arrange: a report input modeled after the user-provided painful output: unavailable macro, no ranked candidates, multiple exclusion counts including missing PEG/OpenDART/net-income growth/ROE/debt ratio, portfolio row warnings, pykrx/universe warning, and Telegram status.
- Act: render report.
- Assert:
  - The report contains a useful `검증 필요` section capped to 3 tasks.
  - The report contains an `운영 상태` section with Telegram status.
  - The report does not expose raw `False`, `None`, or named internal diagnostic keys in normal user-facing lines.
  - Empty candidate text explains the data-quality blockers and next verification actions.

### T9. IP change is actionable verification
- Arrange: `portfolio.ip_changed_flag=True` and Telegram status set.
- Act: render report.
- Assert:
  - IP change appears in `검증 필요` or equivalent actionable verification guidance.
  - Telegram status remains in `운영 상태` only.

## Verification Commands
- `python3 -m pytest`

## Non-test Checks
- Review report text manually for Korean clarity and non-advisory wording.
- Confirm no source files outside planned reporting/test/docs scope were modified during implementation.
