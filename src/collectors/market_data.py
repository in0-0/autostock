from __future__ import annotations

import json
import hashlib
import math
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from src.models import FundamentalRecord, TechnicalRecord
from src.utils.atomic import atomic_write_json


MARKET_DATA_CACHE_SCHEMA_VERSION = 2


@dataclass
class ProviderTelemetry:
    provider: str
    success: bool
    message: str = ""


@dataclass(frozen=True)
class DailyPriceRow:
    trade_date: date
    close: float
    volume: float


@dataclass(frozen=True)
class NormalizedTechnicalSeries:
    monthly_close: list[float]
    weekly_close: list[float]
    weekly_volume: list[float]
    listed_weeks: int


@dataclass
class MarketDataBundle:
    fundamentals: list[FundamentalRecord]
    technicals: dict[str, TechnicalRecord]
    macro: dict
    provider: str
    current_prices: dict[str, int] = field(default_factory=dict)
    telemetry: list[ProviderTelemetry] = field(default_factory=list)
    stale_warnings: list[str] = field(default_factory=list)
    macro_provider: str | None = None


class MarketDataProvider(Protocol):
    name: str

    def load(self) -> MarketDataBundle:
        raise NotImplementedError


class SampleMarketDataProvider:
    name = "sample"

    def load(self) -> MarketDataBundle:
        technicals = load_sample_technicals()
        return MarketDataBundle(
            fundamentals=load_sample_fundamentals(),
            technicals=technicals,
            macro=load_sample_macro(),
            provider=self.name,
            current_prices={ticker: int(record.weekly_close[-1]) for ticker, record in technicals.items()},
            telemetry=[ProviderTelemetry(provider=self.name, success=True)],
            macro_provider=self.name,
        )


class FixtureMarketDataProvider:
    name = "fixture"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path).expanduser()

    def load(self) -> MarketDataBundle:
        with self.fixture_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        fundamentals = [FundamentalRecord(**record) for record in payload.get("fundamentals", [])]
        technicals = {
            ticker: TechnicalRecord(**record)
            for ticker, record in payload.get("technicals", {}).items()
        }
        current_prices = {
            str(ticker): int(price)
            for ticker, price in payload.get("current_prices", {}).items()
        }
        provider_name = str(payload.get("provider", self.name))
        macro, macro_provider, macro_warnings = _macro_from_payload(payload, provider_name)
        return MarketDataBundle(
            fundamentals=fundamentals,
            technicals=technicals,
            macro=macro,
            provider=provider_name,
            current_prices=current_prices,
            telemetry=[ProviderTelemetry(provider=provider_name, success=True)],
            stale_warnings=[*list(payload.get("stale_warnings", [])), *macro_warnings],
            macro_provider=macro_provider,
        )


class CachedMarketDataProvider:
    def __init__(self, provider: MarketDataProvider, cache_path: str | Path, max_age_days: int = 1) -> None:
        self.provider = provider
        self.cache_path = Path(cache_path)
        self.max_age_days = max_age_days
        self.name = provider.name

    def load(self) -> MarketDataBundle:
        cached = self._read_cache()
        if cached is not None:
            cached.telemetry.append(ProviderTelemetry(provider=f"{self.name}_cache", success=True))
            return cached

        bundle = self.provider.load()
        atomic_write_json(self.cache_path, _bundle_to_payload(bundle, written_at=datetime.now()))
        return bundle

    def _read_cache(self) -> MarketDataBundle | None:
        if not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if not _cache_is_fresh(payload, self.max_age_days):
                return None
            return _bundle_from_payload(payload)
        except Exception:
            return None


class PykrxMarketDataProvider:
    name = "pykrx"

    def __init__(
        self,
        universe: list[str] | None = None,
        lookback_days: int = 460,
        request_delay_seconds: float = 0.0,
    ) -> None:
        self.universe = universe or []
        self.lookback_days = lookback_days
        self.request_delay_seconds = request_delay_seconds

    def load(self) -> MarketDataBundle:
        if not self.universe:
            raise RuntimeError("market_data.universe is required for pykrx real mode")

        fundamentals: list[FundamentalRecord] = []
        technicals: dict[str, TechnicalRecord] = {}
        current_prices: dict[str, int] = {}

        for ticker in self.universe:
            price_rows = self._load_price_rows(ticker)
            if not price_rows:
                continue

            normalized = _normalize_daily_ohlcv(price_rows)
            current_prices[ticker] = int(price_rows[-1].close)
            technicals[ticker] = TechnicalRecord(
                ticker=ticker,
                monthly_close=normalized.monthly_close,
                weekly_close=normalized.weekly_close,
                weekly_volume=normalized.weekly_volume,
                listed_weeks=normalized.listed_weeks,
            )
            name = self._ticker_name(ticker)
            fundamentals.append(_incomplete_fundamental(ticker, name))
            _sleep_between_provider_requests(self.request_delay_seconds)

        if not technicals:
            raise RuntimeError("pykrx returned no usable OHLCV rows")
        return MarketDataBundle(
            fundamentals=fundamentals,
            technicals=technicals,
            macro=load_unavailable_macro(),
            provider=self.name,
            current_prices=current_prices,
            telemetry=[ProviderTelemetry(provider=self.name, success=True)],
            stale_warnings=["missing_full_fundamental_fields:pykrx", "macro_data_unavailable:pykrx"],
            macro_provider="unavailable",
        )

    def _load_price_rows(self, ticker: str) -> list[DailyPriceRow]:
        try:
            from pykrx import stock
        except ImportError as exc:  # pragma: no cover - optional runtime package.
            raise RuntimeError("pykrx is not installed") from exc
        end = date.today()
        start = end - timedelta(days=self.lookback_days)
        ohlcv = stock.get_market_ohlcv_by_date(_yyyymmdd(start), _yyyymmdd(end), ticker)
        return _daily_price_rows(ohlcv, ["종가", "Close", "close"], ["거래량", "Volume", "volume"])

    def _ticker_name(self, ticker: str) -> str:
        try:
            from pykrx import stock
        except ImportError:
            return ticker
        return stock.get_market_ticker_name(ticker) or ticker


class FinanceDataReaderMarketDataProvider:
    name = "fdr"

    def __init__(
        self,
        universe: list[str] | None = None,
        lookback_days: int = 460,
        request_delay_seconds: float = 0.0,
    ) -> None:
        self.universe = universe or []
        self.lookback_days = lookback_days
        self.request_delay_seconds = request_delay_seconds

    def load(self) -> MarketDataBundle:
        if not self.universe:
            raise RuntimeError("market_data.universe is required for FinanceDataReader real mode")

        fundamentals: list[FundamentalRecord] = []
        technicals: dict[str, TechnicalRecord] = {}
        current_prices: dict[str, int] = {}

        for ticker in self.universe:
            price_rows = self._load_price_rows(ticker)
            if not price_rows:
                continue

            normalized = _normalize_daily_ohlcv(price_rows)
            current_prices[ticker] = int(price_rows[-1].close)
            technicals[ticker] = TechnicalRecord(
                ticker=ticker,
                monthly_close=normalized.monthly_close,
                weekly_close=normalized.weekly_close,
                weekly_volume=normalized.weekly_volume,
                listed_weeks=normalized.listed_weeks,
            )
            fundamentals.append(_incomplete_fundamental(ticker, ticker))
            _sleep_between_provider_requests(self.request_delay_seconds)

        if not technicals:
            raise RuntimeError("FinanceDataReader returned no usable OHLCV rows")
        return MarketDataBundle(
            fundamentals=fundamentals,
            technicals=technicals,
            macro=load_unavailable_macro(),
            provider=self.name,
            current_prices=current_prices,
            telemetry=[ProviderTelemetry(provider=self.name, success=True)],
            stale_warnings=["missing_full_fundamental_fields:fdr", "macro_data_unavailable:fdr"],
            macro_provider="unavailable",
        )

    def _load_price_rows(self, ticker: str) -> list[DailyPriceRow]:
        try:
            import FinanceDataReader as fdr
        except ImportError as exc:  # pragma: no cover - optional runtime package.
            raise RuntimeError("FinanceDataReader is not installed") from exc
        start = date.today() - timedelta(days=self.lookback_days)
        frame = fdr.DataReader(ticker, start.isoformat())
        return _daily_price_rows(frame, ["Close", "종가", "close"], ["Volume", "거래량", "volume"])


class NaverMarketDataProvider:
    name = "naver"

    def __init__(self, universe: list[str] | None = None) -> None:
        self.universe = universe or []

    def load(self) -> MarketDataBundle:
        raise RuntimeError("Naver fallback is last-resort only and requires a dedicated parser")


def load_market_data_with_fallback(providers: list[MarketDataProvider]) -> MarketDataBundle:
    telemetry: list[ProviderTelemetry] = []
    for provider in providers:
        try:
            bundle = provider.load()
        except Exception as exc:
            telemetry.append(ProviderTelemetry(provider=provider.name, success=False, message=_sanitize_error_message(exc)))
            continue
        bundle.telemetry = [*telemetry, *bundle.telemetry]
        return bundle
    return MarketDataBundle(
        fundamentals=[],
        technicals={},
        macro=load_unavailable_macro(),
        provider="none",
        current_prices={},
        telemetry=telemetry,
        stale_warnings=["all_market_data_providers_failed", "macro_data_unavailable:none"],
        macro_provider="unavailable",
    )


def build_market_data_providers(
    mode: str,
    universe: list[str] | None = None,
    lookback_days: int = 460,
    fixture_path: str | None = None,
    request_delay_seconds: float = 0.0,
    cache_dir: str | None = None,
    cache_max_age_days: int = 1,
) -> list[MarketDataProvider]:
    if mode == "sample":
        return [SampleMarketDataProvider()]
    if mode == "fixture":
        if not fixture_path:
            raise ValueError("market_data.fixture_path is required for fixture mode")
        return [FixtureMarketDataProvider(fixture_path)]
    if mode == "real":
        providers: list[MarketDataProvider] = [
            PykrxMarketDataProvider(universe, lookback_days, request_delay_seconds),
            FinanceDataReaderMarketDataProvider(universe, lookback_days, request_delay_seconds),
            NaverMarketDataProvider(universe),
        ]
        if cache_dir:
            return [
                CachedMarketDataProvider(
                    provider,
                    _cache_path(cache_dir, provider.name, universe or [], lookback_days),
                    cache_max_age_days,
                )
                for provider in providers
            ]
        return providers
    raise ValueError(f"unsupported market_data.mode: {mode}")


def market_data_warning_messages(bundle: MarketDataBundle) -> list[str]:
    warnings = list(bundle.stale_warnings)
    warnings.extend(
        f"market_provider_failed:{entry.provider}:{entry.message}"
        for entry in bundle.telemetry
        if not entry.success
    )
    return warnings


def candidate_completeness_warnings(
    fundamental: FundamentalRecord,
    technical: TechnicalRecord | None,
    current_price: int | None,
    *,
    provider: str,
    provider_warnings: list[str] | None = None,
) -> list[str]:
    warnings: list[str] = []
    if current_price is None or current_price <= 0:
        warnings.append("missing_current_price")
    if technical is None:
        warnings.append("missing_technical_data")
    else:
        if len(technical.weekly_close) < 20:
            warnings.append("stale_or_short_weekly_series")
        if len(technical.monthly_close) < 20:
            warnings.append("stale_or_short_monthly_series")
    if fundamental.peg <= 0:
        warnings.append("missing_or_invalid_peg")
    if fundamental.roe_3y_avg <= 0 or fundamental.operating_margin <= 0 or fundamental.debt_ratio >= 999:
        warnings.append("missing_full_fundamental_fields")
    if not provider or provider == "none":
        warnings.append("missing_provider_provenance")
    for provider_warning in provider_warnings or []:
        if provider_warning.startswith(("stale_", "missing_full_fundamental_fields", "macro_data_unavailable")):
            warnings.append(f"provider_warning:{provider_warning}")
    return warnings


def _yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _daily_price_rows(frame: object, close_names: list[str], volume_names: list[str]) -> list[DailyPriceRow]:
    close_series = _series(frame, close_names)
    volume_series = _series(frame, volume_names)
    if close_series is None:
        raise ValueError("market_data_provider_missing_close")
    if volume_series is None:
        raise ValueError("market_data_provider_missing_volume")
    index_values = _index_values(frame)
    if not index_values:
        raise ValueError("market_data_provider_missing_date_index")

    close_values = _series_items(close_series)
    volume_values = _series_items(volume_series)
    if len(index_values) != len(close_values) or len(close_values) != len(volume_values):
        raise ValueError("market_data_provider_misaligned_ohlcv")

    rows: list[DailyPriceRow] = []
    for raw_date, raw_close, raw_volume in zip(index_values, close_values, volume_values):
        if _is_missing_series_value(raw_close) or _is_missing_series_value(raw_volume):
            continue
        trade_date = _coerce_trade_date(raw_date)
        rows.append(DailyPriceRow(trade_date=trade_date, close=float(raw_close), volume=float(raw_volume)))
    rows.sort(key=lambda row: row.trade_date)
    return rows


def _normalize_daily_ohlcv(rows: list[DailyPriceRow]) -> NormalizedTechnicalSeries:
    if not rows:
        return NormalizedTechnicalSeries(monthly_close=[], weekly_close=[], weekly_volume=[], listed_weeks=0)

    monthly_close_by_bucket: dict[tuple[int, int], float] = {}
    weekly_close_by_bucket: dict[tuple[int, int], float] = {}
    weekly_volume_by_bucket: dict[tuple[int, int], float] = {}

    for row in sorted(rows, key=lambda item: item.trade_date):
        month_bucket = (row.trade_date.year, row.trade_date.month)
        iso_year, iso_week, _ = row.trade_date.isocalendar()
        week_bucket = (iso_year, iso_week)
        monthly_close_by_bucket[month_bucket] = row.close
        weekly_close_by_bucket[week_bucket] = row.close
        weekly_volume_by_bucket[week_bucket] = weekly_volume_by_bucket.get(week_bucket, 0.0) + row.volume

    monthly_close = [monthly_close_by_bucket[bucket] for bucket in sorted(monthly_close_by_bucket)]
    weekly_buckets = sorted(weekly_close_by_bucket)
    weekly_close = [weekly_close_by_bucket[bucket] for bucket in weekly_buckets]
    weekly_volume = [weekly_volume_by_bucket[bucket] for bucket in weekly_buckets]
    return NormalizedTechnicalSeries(
        monthly_close=_tail(monthly_close, 24),
        weekly_close=_tail(weekly_close, 80),
        weekly_volume=_tail(weekly_volume, 80),
        listed_weeks=len(weekly_buckets),
    )


def _series(frame: object, names: list[str]) -> object | None:
    for name in names:
        try:
            return frame[name]  # type: ignore[index]
        except Exception:
            continue
    return None


def _series_values(frame: object, names: list[str]) -> list[float]:
    series = _series(frame, names)
    if series is None:
        return []
    return [float(value) for value in _series_items(series) if not _is_missing_series_value(value)]


def _series_items(series: object) -> list[object]:
    try:
        return series.tolist()  # type: ignore[attr-defined]
    except AttributeError:
        return list(series)  # type: ignore[arg-type]


def _is_missing_series_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)
    try:
        return bool(value != value)
    except Exception:
        return False


def _index_values(frame: object) -> list[object]:
    try:
        return list(frame.index)  # type: ignore[attr-defined]
    except AttributeError:
        return []


def _coerce_trade_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    date_method = getattr(value, "date", None)
    if callable(date_method):
        coerced = date_method()
        if isinstance(coerced, date):
            return coerced
    raise ValueError("market_data_provider_missing_date_index")


def _tail(values: list[float], size: int) -> list[float]:
    return values[-size:] if len(values) > size else values


def _sleep_between_provider_requests(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def _cache_path(cache_dir: str | Path, provider_name: str, universe: list[str], lookback_days: int) -> Path:
    key = hashlib.sha256("|".join([provider_name, str(lookback_days), *universe]).encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir).expanduser() / f"{provider_name}_{key}.json"


def _bundle_to_payload(bundle: MarketDataBundle, *, written_at: datetime | None = None) -> dict:
    return {
        "cache_schema_version": MARKET_DATA_CACHE_SCHEMA_VERSION,
        "cache_written_at": (written_at or datetime.now()).isoformat(),
        "fundamentals": [record.model_dump() for record in bundle.fundamentals],
        "technicals": {ticker: record.model_dump() for ticker, record in bundle.technicals.items()},
        "macro": bundle.macro,
        "provider": bundle.provider,
        "current_prices": bundle.current_prices,
        "telemetry": [asdict(entry) for entry in bundle.telemetry],
        "stale_warnings": bundle.stale_warnings,
        "macro_provider": bundle.macro_provider,
    }


def _bundle_from_payload(payload: dict) -> MarketDataBundle:
    if payload.get("cache_schema_version") != MARKET_DATA_CACHE_SCHEMA_VERSION:
        raise ValueError("invalid_market_cache_schema_version")
    if "macro" not in payload or "macro_provider" not in payload:
        raise ValueError("invalid_market_cache_macro")
    return MarketDataBundle(
        fundamentals=[FundamentalRecord(**record) for record in payload.get("fundamentals", [])],
        technicals={
            ticker: TechnicalRecord(**record)
            for ticker, record in payload.get("technicals", {}).items()
        },
        macro=payload["macro"],
        provider=str(payload.get("provider", "cache")),
        current_prices={str(ticker): int(price) for ticker, price in payload.get("current_prices", {}).items()},
        telemetry=[ProviderTelemetry(**entry) for entry in payload.get("telemetry", [])],
        stale_warnings=list(payload.get("stale_warnings", [])),
        macro_provider=payload.get("macro_provider"),
    )


def _cache_is_fresh(payload: dict, max_age_days: int) -> bool:
    if max_age_days < 0:
        return False
    written_at = payload.get("cache_written_at")
    if not written_at:
        return False
    try:
        cached_at = datetime.fromisoformat(str(written_at))
    except ValueError:
        return False
    return datetime.now() - cached_at <= timedelta(days=max_age_days)


def _macro_from_payload(payload: dict, provider_name: str) -> tuple[dict, str, list[str]]:
    if "macro" not in payload:
        return load_unavailable_macro(), "unavailable", [f"macro_data_unavailable:{provider_name}"]
    return payload["macro"], str(payload.get("macro_provider", provider_name)), []


def _sanitize_error_message(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    message = re.sub(r"https?://\S+", "[url]", message)
    message = re.sub(r"(/Users/\S+|/private/\S+|/var/\S+|[A-Za-z]:\\\S+)", "[path]", message)
    message = re.sub(
        r"(?i)(?:^|(?<=\s))((?:\.{1,2}/)?(?:[\w.-]+/)*[\w.-]*(?:credential|secret|token|service-account|account)[\w.-]*\.(?:json|ya?ml|toml|env|txt))",
        "[path]",
        message,
    )
    secret_key_pattern = (
        r"(?i)\b(token|secret|credential|credentials_path|credential_path|password|api[_-]?key|"
        r"spreadsheet[_-]?id|sheet[_-]?id|account[_-]?id|chat[_-]?id|client[_-]?email)\b"
        r"\s*(?:=|:)?\s*[^\s,;]+"
    )
    message = re.sub(secret_key_pattern, lambda match: f"{match.group(1)}=[redacted]", message)
    message = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[id]", message)
    return message


def _incomplete_fundamental(ticker: str, name: str) -> FundamentalRecord:
    return FundamentalRecord(
        ticker=ticker,
        name=name,
        industry="DEFAULT",
        roe_3y_avg=0.0,
        debt_ratio=999.0,
        operating_margin=0.0,
        net_income_growth=0.0,
        operating_income_growth=0.0,
        previous_net_income=0,
        current_net_income=0,
        peg=0.0,
    )


def load_sample_fundamentals() -> list[FundamentalRecord]:
    return [
        FundamentalRecord(
            ticker="005930",
            name="삼성전자",
            industry="MANUFACTURING",
            roe_3y_avg=0.12,
            debt_ratio=0.31,
            operating_margin=0.11,
            net_income_growth=0.18,
            operating_income_growth=0.16,
            previous_net_income=10_000,
            current_net_income=11_800,
            peg=0.42,
        ),
        FundamentalRecord(
            ticker="005380",
            name="현대차",
            industry="MANUFACTURING",
            roe_3y_avg=0.13,
            debt_ratio=1.21,
            operating_margin=0.08,
            net_income_growth=0.20,
            operating_income_growth=0.18,
            previous_net_income=8_000,
            current_net_income=9_600,
            peg=0.58,
        ),
        FundamentalRecord(
            ticker="035420",
            name="NAVER",
            industry="SOFTWARE",
            roe_3y_avg=0.11,
            debt_ratio=0.42,
            operating_margin=0.18,
            net_income_growth=0.16,
            operating_income_growth=0.15,
            previous_net_income=6_000,
            current_net_income=6_960,
            peg=0.76,
        ),
        FundamentalRecord(
            ticker="000660",
            name="SK하이닉스",
            industry="MANUFACTURING",
            roe_3y_avg=0.16,
            debt_ratio=0.74,
            operating_margin=0.20,
            net_income_growth=0.55,
            operating_income_growth=0.52,
            previous_net_income=7_000,
            current_net_income=10_850,
            peg=1.62,
        ),
        FundamentalRecord(
            ticker="051910",
            name="LG화학",
            industry="MANUFACTURING",
            roe_3y_avg=0.12,
            debt_ratio=0.82,
            operating_margin=0.07,
            net_income_growth=0.14,
            operating_income_growth=0.13,
            previous_net_income=5_000,
            current_net_income=5_700,
            peg=0.64,
        ),
        FundamentalRecord(
            ticker="068270",
            name="셀트리온",
            industry="DEFAULT",
            roe_3y_avg=0.15,
            debt_ratio=0.38,
            operating_margin=0.29,
            net_income_growth=0.19,
            operating_income_growth=0.17,
            previous_net_income=4_000,
            current_net_income=4_760,
            peg=0.69,
        ),
    ]


def load_sample_technicals() -> dict[str, TechnicalRecord]:
    monthly_uptrend = [90, 92, 94, 96, 99, 101, 104, 106, 108, 111, 114, 117, 119, 121, 124, 126, 129, 132, 134, 137, 140]
    weekly_pullback_20 = [100 + i for i in range(19)] + [112]
    weekly_pullback_60 = [90 + i * 1.1 for i in range(80)]
    weekly_pullback_60[-1] = sum(weekly_pullback_60[-60:]) / 60 * 1.02
    volume_down = [1_000_000, 1_100_000, 1_050_000, 980_000, 900_000] * 20
    volume_down[-1] = 800_000

    return {
        "005930": TechnicalRecord(
            ticker="005930",
            monthly_close=monthly_uptrend,
            weekly_close=weekly_pullback_20,
            weekly_volume=volume_down[-20:],
            listed_weeks=1000,
        ),
        "005380": TechnicalRecord(
            ticker="005380",
            monthly_close=monthly_uptrend,
            weekly_close=weekly_pullback_60,
            weekly_volume=volume_down[-80:],
            listed_weeks=1200,
        ),
        "035420": TechnicalRecord(
            ticker="035420",
            monthly_close=monthly_uptrend,
            weekly_close=weekly_pullback_20,
            weekly_volume=volume_down[-20:],
            listed_weeks=900,
        ),
        "000660": TechnicalRecord(
            ticker="000660",
            monthly_close=monthly_uptrend,
            weekly_close=weekly_pullback_20,
            weekly_volume=volume_down[-20:],
            listed_weeks=1000,
        ),
        "051910": TechnicalRecord(
            ticker="051910",
            monthly_close=monthly_uptrend,
            weekly_close=weekly_pullback_20,
            weekly_volume=volume_down[-20:],
            listed_weeks=1300,
        ),
        "068270": TechnicalRecord(
            ticker="068270",
            monthly_close=monthly_uptrend,
            weekly_close=weekly_pullback_20,
            weekly_volume=volume_down[-20:],
            listed_weeks=1100,
        ),
    }


def load_sample_macro() -> dict:
    return {
        "kospi_monthly_close": [2500, 2520, 2540, 2580, 2600, 2640, 2660, 2680, 2710, 2740, 2760],
        "kosdaq_monthly_close": [800, 810, 820, 835, 840, 850, 860, 870, 882, 895, 905],
        "us_rate": 0.0525,
        "yield_curve_10y2y": -0.0012,
    }


def load_unavailable_macro() -> dict:
    return {
        "kospi_monthly_close": [],
        "kosdaq_monthly_close": [],
        "us_rate": None,
        "yield_curve_10y2y": None,
    }
