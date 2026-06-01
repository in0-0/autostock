from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree

import requests

from src.collectors.universe import SOURCE_RISK_OFFICIAL_API, UniverseRecord
from src.models import FundamentalRecord
from src.utils.atomic import atomic_write_json
from src.utils.redaction import sanitize_error_message

DART_CORP_CODE_CACHE_SCHEMA_VERSION = 1
DART_FINANCIAL_CACHE_SCHEMA_VERSION = 1
DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_FINANCIAL_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"


@dataclass(frozen=True)
class FinancialExclusion:
    ticker: str
    reason: str
    source: str = "opendart"
    detail: str = ""


@dataclass
class DartFinancialResult:
    fundamentals: list[FundamentalRecord] = field(default_factory=list)
    exclusions: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class DartCorpCodeCache:
    def __init__(self, cache_path: str | Path, api_key: str, max_age_days: int = 30, stale_grace_days: int = 90) -> None:
        self.cache_path = Path(cache_path).expanduser()
        self.api_key = api_key
        self.max_age_days = max_age_days
        self.stale_grace_days = stale_grace_days
        self.last_cache_status = "miss"

    def load(self) -> dict[str, str]:
        cached = self._read_cache(self.max_age_days)
        if cached is not None:
            self.last_cache_status = "hit"
            return cached
        try:
            response = requests.get(DART_CORP_CODE_URL, params={"crtfc_key": self.api_key}, timeout=20)
            response.raise_for_status()
            mapping = parse_corp_code_zip(response.content)
        except Exception:
            stale = self._read_cache(self.stale_grace_days)
            if stale is not None:
                self.last_cache_status = "stale"
                return stale
            raise
        self.last_cache_status = "refreshed"
        atomic_write_json(
            self.cache_path,
            {
                "cache_schema_version": DART_CORP_CODE_CACHE_SCHEMA_VERSION,
                "cache_written_at": datetime.now().isoformat(),
                "source": "opendart_corp_code",
                "source_risk": SOURCE_RISK_OFFICIAL_API,
                "mapping": mapping,
            },
        )
        return mapping

    def _read_cache(self, max_age_days: int) -> dict[str, str] | None:
        if max_age_days < 0 or not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if payload.get("cache_schema_version") != DART_CORP_CODE_CACHE_SCHEMA_VERSION:
                return None
            written_at = datetime.fromisoformat(str(payload["cache_written_at"]))
            if datetime.now() - written_at > timedelta(days=max_age_days):
                return None
            return {str(k).zfill(6): str(v) for k, v in payload.get("mapping", {}).items()}
        except Exception:
            return None


class DartFinancialProvider:
    name = "opendart"

    def __init__(
        self,
        api_key: str = "",
        corp_code_mapping: dict[str, str] | None = None,
        api_get: Callable[..., object] | None = None,
        bsns_year: str | None = None,
        reprt_code: str = "11011",
    ) -> None:
        self.api_key = api_key
        self.corp_code_mapping = {str(k).zfill(6): str(v) for k, v in (corp_code_mapping or {}).items()}
        self.api_get = api_get or requests.get
        self.bsns_year = bsns_year or str(datetime.now().year - 1)
        self.reprt_code = reprt_code

    def load_for_universe(
        self,
        universe: list[UniverseRecord],
        *,
        market_metrics: dict[str, dict] | None = None,
    ) -> DartFinancialResult:
        if not self.api_key:
            return DartFinancialResult(
                exclusions={record.ticker: ["dart_api_key_missing"] for record in universe},
                warnings=["dart_api_key_missing"],
            )
        metrics = market_metrics or {}
        result = DartFinancialResult()
        for record in universe:
            corp_code = self.corp_code_mapping.get(record.ticker)
            if not corp_code:
                result.exclusions.setdefault(record.ticker, []).append("missing_dart_corp_code")
                continue
            try:
                rows = self._fetch_financial_rows(corp_code)
                normalized, exclusions = normalize_dart_fundamental(
                    ticker=record.ticker,
                    name=record.name,
                    rows=rows,
                    per=metrics.get(record.ticker, {}).get("per"),
                    collected_at=datetime.now().isoformat(),
                    period=self.bsns_year,
                )
            except Exception as exc:
                result.exclusions.setdefault(record.ticker, []).append("provider_failed:opendart:" + sanitize_error_message(exc))
                continue
            if normalized is None:
                result.exclusions.setdefault(record.ticker, []).extend(exclusions)
            else:
                result.fundamentals.append(normalized)
        return result

    def _fetch_financial_rows(self, corp_code: str) -> list[dict]:
        response = self.api_get(
            DART_FINANCIAL_URL,
            params={
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bsns_year": self.bsns_year,
                "reprt_code": self.reprt_code,
                "fs_div": "CFS",
            },
            timeout=20,
        )
        payload = response.json() if hasattr(response, "json") else response
        if str(payload.get("status", "000")) not in {"000", "0"}:
            raise RuntimeError(f"dart_status:{payload.get('status')}")
        rows = payload.get("list", [])
        if not isinstance(rows, list):
            raise RuntimeError("dart_financial_rows_missing")
        return [dict(row) for row in rows]


def parse_corp_code_zip(content: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        xml_name = archive.namelist()[0]
        root = ElementTree.fromstring(archive.read(xml_name))
    mapping: dict[str, str] = {}
    for item in root.findall(".//list"):
        corp_code = _child_text(item, "corp_code")
        stock_code = _child_text(item, "stock_code")
        if corp_code and stock_code:
            mapping[stock_code.zfill(6)] = corp_code
    return mapping


def normalize_dart_fundamental(
    *,
    ticker: str,
    name: str,
    rows: list[dict],
    per: float | int | None,
    collected_at: str,
    period: str,
) -> tuple[FundamentalRecord | None, list[str]]:
    account_values = _account_value_map(rows)
    exclusions: list[str] = []

    revenue = _find_current(account_values, ["매출액", "수익(매출액)", "영업수익"])
    op_current, op_prev = _find_current_previous(account_values, ["영업이익", "영업이익(손실)"])
    net_current, net_prev, net_before = _find_three_years(account_values, ["당기순이익", "당기순이익(손실)", "연결당기순이익"])
    liabilities = _find_current(account_values, ["부채총계"])
    equity_current, equity_prev, equity_before = _find_three_years(account_values, ["자본총계"])

    if net_prev is None:
        exclusions.append("missing_previous_net_income")
    if net_current is None:
        exclusions.append("missing_current_net_income")
    if op_current is None:
        exclusions.append("missing_operating_profit")
    if revenue in (None, 0):
        exclusions.append("missing_revenue")
    if liabilities is None or equity_current in (None, 0):
        exclusions.append("missing_debt_ratio_inputs")
    valid_roe_inputs = [(net_current, equity_current), (net_prev, equity_prev), (net_before, equity_before)]
    valid_roe = [(n, e) for n, e in valid_roe_inputs if n is not None and e not in (None, 0)]
    if len(valid_roe) < 2:
        exclusions.append("missing_roe_inputs")
    if op_prev in (None, 0) or op_current is None:
        exclusions.append("missing_operating_income_growth_inputs")
    if net_prev in (None, 0) or net_current is None:
        exclusions.append("missing_net_income_growth_inputs")

    net_income_growth = _growth(net_current, net_prev)
    operating_income_growth = _growth(op_current, op_prev)
    if per is None or net_income_growth is None or operating_income_growth is None:
        exclusions.append("missing_peg_inputs")

    if exclusions:
        return None, list(dict.fromkeys(exclusions))

    assert net_current is not None and net_prev is not None
    assert op_current is not None and revenue is not None and liabilities is not None and equity_current is not None
    assert net_income_growth is not None and operating_income_growth is not None and per is not None
    roe_3y_avg = sum(n / e for n, e in valid_roe) / len(valid_roe)
    operating_margin = op_current / revenue
    debt_ratio = liabilities / equity_current
    growth_percent = max(net_income_growth, operating_income_growth) * 100
    peg = float(per) / growth_percent if growth_percent > 0 else 0.0
    if peg <= 0:
        return None, ["missing_peg_inputs"]

    return (
        FundamentalRecord(
            ticker=ticker,
            name=name,
            industry="DEFAULT",
            roe_3y_avg=roe_3y_avg,
            debt_ratio=debt_ratio,
            operating_margin=operating_margin,
            net_income_growth=net_income_growth,
            operating_income_growth=operating_income_growth,
            previous_net_income=int(net_prev),
            current_net_income=int(net_current),
            peg=peg,
            period=period,
            source="opendart",
            source_risk=SOURCE_RISK_OFFICIAL_API,
            collected_at=collected_at,
            field_provenance={
                "revenue": "opendart:annual:revenue",
                "operating_profit": "opendart:annual:operating_profit",
                "net_income": "opendart:annual:net_income",
                "liabilities": "opendart:annual:liabilities",
                "equity": "opendart:annual:equity",
                "per": "market_metric:per",
            },
        ),
        [],
    )


def _account_value_map(rows: list[dict]) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, float]] = {}
    for row in rows:
        account = str(row.get("account_nm") or row.get("account_name") or "").strip()
        if not account:
            continue
        values[account] = {
            "current": _parse_amount(row.get("thstrm_amount")),
            "previous": _parse_amount(row.get("frmtrm_amount")),
            "before_previous": _parse_amount(row.get("bfefrmtrm_amount")),
        }
    return values


def _find_current(values: dict[str, dict[str, float]], aliases: list[str]) -> float | None:
    for alias in aliases:
        value = values.get(alias, {}).get("current")
        if value is not None:
            return value
    return None


def _find_current_previous(values: dict[str, dict[str, float]], aliases: list[str]) -> tuple[float | None, float | None]:
    for alias in aliases:
        row = values.get(alias)
        if row:
            return row.get("current"), row.get("previous")
    return None, None


def _find_three_years(values: dict[str, dict[str, float]], aliases: list[str]) -> tuple[float | None, float | None, float | None]:
    for alias in aliases:
        row = values.get(alias)
        if row:
            return row.get("current"), row.get("previous"), row.get("before_previous")
    return None, None, None


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


def _parse_amount(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        text = str(value).replace(",", "").replace(" ", "")
        if text.startswith("(") and text.endswith(")"):
            text = "-" + text[1:-1]
        return float(text)
    except ValueError:
        return None


def _child_text(item: ElementTree.Element, name: str) -> str:
    child = item.find(name)
    return (child.text or "").strip() if child is not None else ""
