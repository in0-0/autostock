from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.collectors.portfolio_source import (
    PortfolioSourcePosition,
    PortfolioSourceResult,
    PortfolioSourceSnapshot,
)

READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"

HEADER_ALIASES = {
    "기준일": "as_of",
    "증권사": "broker",
    "계좌명": "account_name",
    "계좌유형": "account_type",
    "시장": "market",
    "종목코드": "stock_code",
    "종목명": "stock_name",
    "티커": "ticker",
    "자산군": "asset_class",
    "섹터": "sector",
    "통화": "currency",
    "보유수량": "quantity",
    "평균매수가": "average_price",
    "총매수금액": "total_purchase_amount",
    "현재가": "current_price",
    "평가금액": "market_value",
    "평가손익": "profit_loss",
    "수익률": "return_rate",
    "전체 포트폴리오 비중": "portfolio_ratio",
    "목표비중": "target_ratio",
    "비중차이": "ratio_gap",
    "배당수익률": "dividend_yield",
    "연간예상배당금": "expected_annual_dividend",
    "투자전략": "strategy",
    "투자근거": "rationale",
    "매수일": "buy_date",
    "보유기간": "holding_period",
    "매수목표가": "target_buy_price",
    "추가매수 기준": "add_buy_rule",
    "손절/매도 기준": "stop_or_sell_rule",
    "리밸런싱 필요 여부": "rebalance_required",
    "메모": "memo",
}


@dataclass
class GoogleSheetsConfig:
    spreadsheet_id: str
    range_name: str
    credentials_path: str | None = None
    token_path: str | None = None
    fixture_path: str | None = None


class GoogleSheetsPortfolioSource:
    source_name = "google_sheets"
    source_type = "google_sheets"

    def __init__(self, config: GoogleSheetsConfig, service: Any | None = None) -> None:
        self.config = config
        self.service = service

    def fetch(self) -> PortfolioSourceResult:
        rows = self._read_rows()
        return parse_portfolio_rows(rows, source_name=self.source_name)

    def _read_rows(self) -> list[list[Any]]:
        if self.config.fixture_path:
            return read_portfolio_rows_fixture(self.config.fixture_path)
        service = self.service or self._build_service()
        response = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=self.config.spreadsheet_id, range=self.config.range_name)
            .execute()
        )
        return response.get("values", [])

    def _build_service(self) -> Any:
        if not self.config.credentials_path:
            raise ValueError("google_sheets.credentials_path is required for live Google Sheets reads")
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - depends on optional runtime packages.
            raise RuntimeError("Google Sheets dependencies are not installed") from exc

        credentials_path = Path(self.config.credentials_path).expanduser()
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=[READONLY_SCOPE],
        )
        return build("sheets", "v4", credentials=credentials)


def parse_portfolio_rows(rows: list[list[Any]], *, source_name: str = "google_sheets") -> PortfolioSourceResult:
    if not rows:
        return PortfolioSourceResult(source_type="google_sheets", warnings=["empty_sheet"])

    headers = [_canonical_header(value) for value in rows[0]]
    positions: list[PortfolioSourcePosition] = []
    warnings: list[str] = []

    for row_number, row in enumerate(rows[1:], start=2):
        record = _record_from_row(headers, row)
        if _is_blank_record(record):
            continue
        try:
            positions.append(_position_from_record(record))
        except ValueError as exc:
            warnings.append(f"row_{row_number}:{exc}")

    snapshot = PortfolioSourceSnapshot(
        source_name=source_name,
        source_type="google_sheets",
        cash=0,
        positions=positions,
    )
    return PortfolioSourceResult(
        snapshots=[snapshot],
        warnings=warnings,
        source_type="google_sheets",
        telemetry={"rows_read": max(len(rows) - 1, 0), "positions_loaded": len(positions)},
    )


def read_portfolio_rows_fixture(path: str | Path) -> list[list[str]]:
    fixture_path = Path(path).expanduser()
    dialect = "excel-tab" if fixture_path.suffix.lower() in {".tsv", ".tab"} else "excel"
    with fixture_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [list(row) for row in csv.reader(handle, dialect=dialect)]


def _canonical_header(value: Any) -> str:
    text = str(value).strip()
    return HEADER_ALIASES.get(text, text)


def _record_from_row(headers: list[str], row: list[Any]) -> dict[str, str]:
    record: dict[str, str] = {}
    for index, header in enumerate(headers):
        value = row[index] if index < len(row) else ""
        record[header] = str(value).strip()
    return record


def _is_blank_record(record: dict[str, str]) -> bool:
    return not any(value.strip() for value in record.values())


def _position_from_record(record: dict[str, str]) -> PortfolioSourcePosition:
    ticker = _normalize_ticker(record.get("stock_code") or record.get("ticker") or "")
    stock_name = record.get("stock_name", "").strip()
    quantity = _parse_required_int(record.get("quantity", ""), "invalid_quantity")
    average_price = _parse_required_int(record.get("average_price", ""), "invalid_average_price")
    current_price = _parse_required_int(record.get("current_price", ""), "invalid_current_price")
    market_value = _parse_optional_int(record.get("market_value", ""), "invalid_market_value")

    if not ticker:
        raise ValueError("missing_ticker")
    if not stock_name:
        raise ValueError("missing_stock_name")
    if quantity <= 0:
        raise ValueError("invalid_quantity")
    if average_price <= 0:
        raise ValueError("invalid_average_price")
    if current_price <= 0:
        if market_value is None:
            raise ValueError("missing_current_price")
        current_price = int(market_value / quantity + 0.5)

    return PortfolioSourcePosition(
        ticker=ticker,
        stock_name=stock_name,
        quantity=quantity,
        average_price=average_price,
        current_price=current_price,
        market_value=market_value,
        metadata={
            "market": record.get("market", ""),
            "asset_class": record.get("asset_class", ""),
            "sector": record.get("sector", ""),
            "currency": record.get("currency", ""),
            "strategy": record.get("strategy", ""),
            "rationale": record.get("rationale", ""),
        },
    )


def _normalize_ticker(value: str) -> str:
    text = value.strip()
    if ":" in text:
        text = text.split(":", 1)[1]
    return text.zfill(6) if text.isdigit() and len(text) < 6 else text


def _parse_required_int(value: str | None, error_code: str) -> int:
    try:
        return _parse_int(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(error_code) from exc


def _parse_optional_int(value: str | None, error_code: str = "invalid_number") -> int | None:
    if not value or not str(value).strip():
        return None
    return _parse_required_int(value, error_code)


def _parse_int(value: str | None) -> int:
    if value is None:
        return 0
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return 0
    return int(float(text))


def parse_percent(value: str | None) -> float | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).replace(",", "").strip()
    if text.endswith("%"):
        return float(text[:-1]) / 100
    parsed = float(text)
    return parsed / 100 if parsed > 1 else parsed
