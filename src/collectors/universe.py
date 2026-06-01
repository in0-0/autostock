from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from src.utils.atomic import atomic_write_json

UNIVERSE_CACHE_SCHEMA_VERSION = 1
SOURCE_RISK_OFFICIAL_API = "official_api"
SOURCE_RISK_PACKAGE_PUBLIC_SOURCE = "package_public_source"


@dataclass(frozen=True)
class UniverseRecord:
    ticker: str
    name: str
    market: str
    source: str
    source_risk: str
    collected_at: str
    listed: bool = True
    metadata: dict = field(default_factory=dict)

    def to_payload(self) -> dict:
        return asdict(self)


class UniverseProvider(Protocol):
    name: str

    def load(self) -> list[UniverseRecord]:
        raise NotImplementedError


@dataclass(frozen=True)
class UniverseFilter:
    markets: tuple[str, ...] = ("KOSPI", "KOSDAQ")
    exclude_etf: bool = True
    exclude_etn: bool = True
    exclude_konex: bool = True
    max_universe_size: int | None = None


class PykrxUniverseProvider:
    name = "pykrx_universe"

    def __init__(self, filter_config: UniverseFilter | None = None) -> None:
        self.filter_config = filter_config or UniverseFilter()

    def load(self) -> list[UniverseRecord]:
        try:
            from pykrx import stock
        except ImportError as exc:  # pragma: no cover - optional runtime package.
            raise RuntimeError("pykrx is not installed") from exc

        collected_at = datetime.now().isoformat()
        records: list[UniverseRecord] = []
        for market in self.filter_config.markets:
            if market == "KONEX" and self.filter_config.exclude_konex:
                continue
            for ticker in stock.get_market_ticker_list(market=market):
                name = stock.get_market_ticker_name(ticker) or ticker
                records.append(
                    UniverseRecord(
                        ticker=_normalize_ticker(ticker),
                        name=str(name),
                        market=market,
                        source=self.name,
                        source_risk=SOURCE_RISK_PACKAGE_PUBLIC_SOURCE,
                        collected_at=collected_at,
                    )
                )
        return apply_universe_filter(records, self.filter_config)


class FdrUniverseProvider:
    name = "fdr_universe"

    def __init__(self, filter_config: UniverseFilter | None = None) -> None:
        self.filter_config = filter_config or UniverseFilter()

    def load(self) -> list[UniverseRecord]:
        try:
            import FinanceDataReader as fdr
        except ImportError as exc:  # pragma: no cover - optional runtime package.
            raise RuntimeError("FinanceDataReader is not installed") from exc

        collected_at = datetime.now().isoformat()
        records: list[UniverseRecord] = []
        listing = fdr.StockListing("KRX")
        rows = _frame_rows(listing)
        for row in rows:
            market = str(row.get("Market") or row.get("market") or "").upper()
            ticker = str(row.get("Code") or row.get("Symbol") or row.get("ticker") or "")
            name = str(row.get("Name") or row.get("name") or ticker)
            if not ticker:
                continue
            records.append(
                UniverseRecord(
                    ticker=_normalize_ticker(ticker),
                    name=name,
                    market=market or "KRX",
                    source=self.name,
                    source_risk=SOURCE_RISK_PACKAGE_PUBLIC_SOURCE,
                    collected_at=collected_at,
                    metadata={"raw_market": market},
                )
            )
        return apply_universe_filter(records, self.filter_config)


class CachedUniverseProvider:
    def __init__(self, provider: UniverseProvider, cache_path: str | Path, max_age_days: int = 7, stale_grace_days: int = 14) -> None:
        self.provider = provider
        self.cache_path = Path(cache_path).expanduser()
        self.max_age_days = max_age_days
        self.stale_grace_days = stale_grace_days
        self.name = provider.name
        self.last_cache_status = "miss"

    def load(self) -> list[UniverseRecord]:
        cached = self._read_cache(max_age_days=self.max_age_days)
        if cached is not None:
            self.last_cache_status = "hit"
            return cached
        try:
            records = self.provider.load()
        except Exception:
            stale = self._read_cache(max_age_days=self.stale_grace_days)
            if stale is not None:
                self.last_cache_status = "stale"
                return stale
            raise
        self.last_cache_status = "refreshed"
        atomic_write_json(self.cache_path, _records_to_payload(records, provider=self.provider.name))
        return records

    def _read_cache(self, *, max_age_days: int) -> list[UniverseRecord] | None:
        if max_age_days < 0 or not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if payload.get("cache_schema_version") != UNIVERSE_CACHE_SCHEMA_VERSION:
                return None
            written_at = datetime.fromisoformat(str(payload["cache_written_at"]))
            if datetime.now() - written_at > timedelta(days=max_age_days):
                return None
            return [UniverseRecord(**record) for record in payload.get("records", [])]
        except Exception:
            return None


def apply_universe_filter(records: list[UniverseRecord], filter_config: UniverseFilter) -> list[UniverseRecord]:
    markets = {market.upper() for market in filter_config.markets}
    filtered: list[UniverseRecord] = []
    seen: set[str] = set()
    for record in sorted(records, key=lambda item: (item.market, item.ticker)):
        market = record.market.upper()
        if market == "KONEX" and filter_config.exclude_konex:
            continue
        if markets and market not in markets:
            continue
        name_upper = record.name.upper()
        if filter_config.exclude_etf and _looks_like_etf(record, name_upper):
            continue
        if filter_config.exclude_etn and _looks_like_etn(record, name_upper):
            continue
        if record.ticker in seen:
            continue
        seen.add(record.ticker)
        filtered.append(record)
    if filter_config.max_universe_size is not None:
        return filtered[: max(0, filter_config.max_universe_size)]
    return filtered


def load_universe_with_fallback(providers: list[UniverseProvider]) -> tuple[list[UniverseRecord], list[str]]:
    warnings: list[str] = []
    for provider in providers:
        try:
            records = provider.load()
        except Exception as exc:
            warnings.append(f"universe_provider_failed:{provider.name}:{_stable_error(exc)}")
            continue
        if records:
            cache_status = getattr(provider, "last_cache_status", None)
            if cache_status == "stale":
                warnings.append("stale_universe_cache")
            return records, warnings
        warnings.append(f"universe_provider_empty:{provider.name}")
    warnings.append("universe_empty")
    return [], warnings


def universe_cache_path(cache_dir: str | Path, provider_name: str, filter_config: UniverseFilter) -> Path:
    key = hashlib.sha256(
        "|".join(
            [
                provider_name,
                ",".join(filter_config.markets),
                str(filter_config.exclude_etf),
                str(filter_config.exclude_etn),
                str(filter_config.exclude_konex),
                str(filter_config.max_universe_size),
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return Path(cache_dir).expanduser() / f"universe_{provider_name}_{key}.json"


def _records_to_payload(records: list[UniverseRecord], *, provider: str) -> dict:
    return {
        "cache_schema_version": UNIVERSE_CACHE_SCHEMA_VERSION,
        "cache_written_at": datetime.now().isoformat(),
        "provider": provider,
        "records": [record.to_payload() for record in records],
    }


def _normalize_ticker(ticker: object) -> str:
    return str(ticker).strip().zfill(6)


def _looks_like_etf(record: UniverseRecord, name_upper: str) -> bool:
    kind = str(record.metadata.get("kind", "")).upper()
    return kind == "ETF" or "ETF" in name_upper or name_upper.startswith(("KODEX", "TIGER", "ACE", "KBSTAR", "HANARO", "ARIRANG", "SOL "))


def _looks_like_etn(record: UniverseRecord, name_upper: str) -> bool:
    kind = str(record.metadata.get("kind", "")).upper()
    return kind == "ETN" or "ETN" in name_upper


def _frame_rows(frame: object) -> list[dict]:
    to_dict = getattr(frame, "to_dict", None)
    if callable(to_dict):
        try:
            rows = to_dict("records")
            if isinstance(rows, list):
                return [dict(row) for row in rows]
        except Exception:
            pass
    if isinstance(frame, list):
        return [dict(row) for row in frame]
    return []


def _stable_error(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return message.splitlines()[0][:120]
