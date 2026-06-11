from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from src.utils.atomic import atomic_write_json
from src.utils.redaction import sanitize_error_message

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
    exclude_non_numeric_ticker: bool = True
    exclude_spac: bool = True
    exclude_preferred_share: bool = True
    exclude_reit_infra_fund: bool = True
    allowlist: tuple[str, ...] = ()
    max_universe_size: int | None = None


@dataclass(frozen=True)
class UniverseFilterResult:
    records: list[UniverseRecord]
    exclusion_counts: dict[str, int] = field(default_factory=dict)
    exclusion_samples: list[dict] = field(default_factory=list)
    allowlist_overrides: dict[str, int] = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "counts": dict(self.exclusion_counts),
            "samples": [dict(sample) for sample in self.exclusion_samples],
            "allowlist_overrides": dict(self.allowlist_overrides),
        }


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
        result = apply_universe_filter_result(records, self.filter_config)
        self.last_filter_summary = result.summary()
        return result.records


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
        result = apply_universe_filter_result(records, self.filter_config)
        self.last_filter_summary = result.summary()
        return result.records


class CachedUniverseProvider:
    def __init__(self, provider: UniverseProvider, cache_path: str | Path, max_age_days: int = 7, stale_grace_days: int = 14) -> None:
        self.provider = provider
        self.cache_path = Path(cache_path).expanduser()
        self.max_age_days = max_age_days
        self.stale_grace_days = stale_grace_days
        self.name = provider.name
        self.last_cache_status = "miss"
        self.last_filter_summary: dict = {}

    def load(self) -> list[UniverseRecord]:
        cached = self._read_cache(max_age_days=self.max_age_days)
        if cached is not None:
            self.last_cache_status = "hit"
            records, summary = cached
            self.last_filter_summary = summary
            return records
        try:
            records = self.provider.load()
        except Exception:
            stale = self._read_cache(max_age_days=self.stale_grace_days)
            if stale is not None:
                self.last_cache_status = "stale"
                records, summary = stale
                self.last_filter_summary = summary
                return records
            raise
        summary = getattr(self.provider, "last_filter_summary", None)
        if not summary:
            filter_config = getattr(self.provider, "filter_config", UniverseFilter())
            result = apply_universe_filter_result(records, filter_config)
            records = result.records
            summary = result.summary()
        self.last_filter_summary = dict(summary)
        self.last_cache_status = "refreshed"
        atomic_write_json(self.cache_path, _records_to_payload(records, provider=self.provider.name, filter_summary=self.last_filter_summary))
        return records

    def _read_cache(self, *, max_age_days: int) -> tuple[list[UniverseRecord], dict] | None:
        if max_age_days < 0 or not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if payload.get("cache_schema_version") != UNIVERSE_CACHE_SCHEMA_VERSION:
                return None
            written_at = datetime.fromisoformat(str(payload["cache_written_at"]))
            if datetime.now() - written_at > timedelta(days=max_age_days):
                return None
            return [UniverseRecord(**record) for record in payload.get("records", [])], dict(payload.get("filter_summary", {}))
        except Exception:
            return None


def apply_universe_filter(records: list[UniverseRecord], filter_config: UniverseFilter) -> list[UniverseRecord]:
    return apply_universe_filter_result(records, filter_config).records


def apply_universe_filter_result(records: list[UniverseRecord], filter_config: UniverseFilter) -> UniverseFilterResult:
    markets = {market.upper() for market in filter_config.markets}
    filtered: list[UniverseRecord] = []
    seen: set[str] = set()
    exclusion_counts: dict[str, int] = {}
    exclusion_samples: list[dict] = []
    allowlist_overrides: dict[str, int] = {}
    allowlist = {_normalize_ticker(ticker) for ticker in filter_config.allowlist}

    for record in sorted(records, key=lambda item: (item.market, item.ticker)):
        reasons = _universe_exclusion_reasons(record, filter_config, markets)
        if reasons and record.ticker in allowlist:
            for reason in reasons:
                allowlist_overrides[reason] = allowlist_overrides.get(reason, 0) + 1
            reasons = []
        if reasons:
            for reason in reasons:
                exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
                if len(exclusion_samples) < 10:
                    exclusion_samples.append(
                        {
                            "ticker": record.ticker,
                            "name": record.name,
                            "market": record.market,
                            "reason": reason,
                        }
                    )
            continue
        if record.ticker in seen:
            continue
        seen.add(record.ticker)
        filtered.append(record)
    if filter_config.max_universe_size is not None:
        filtered = filtered[: max(0, filter_config.max_universe_size)]
    return UniverseFilterResult(
        records=filtered,
        exclusion_counts=dict(sorted(exclusion_counts.items())),
        exclusion_samples=exclusion_samples,
        allowlist_overrides=dict(sorted(allowlist_overrides.items())),
    )


def _universe_exclusion_reasons(record: UniverseRecord, filter_config: UniverseFilter, markets: set[str]) -> list[str]:
    reasons: list[str] = []
    market = record.market.upper()
    if market == "KONEX" and filter_config.exclude_konex:
        reasons.append("konex")
    if markets and market not in markets:
        reasons.append("market_not_allowed")
    name_upper = record.name.upper()
    if filter_config.exclude_etf and _looks_like_etf(record, name_upper):
        reasons.append("etf")
    if filter_config.exclude_etn and _looks_like_etn(record, name_upper):
        reasons.append("etn")
    if filter_config.exclude_non_numeric_ticker and not record.ticker.isdigit():
        reasons.append("non_numeric_ticker")
    if filter_config.exclude_spac and _looks_like_spac(record, name_upper):
        reasons.append("spac")
    if filter_config.exclude_preferred_share and _looks_like_preferred_share(record, name_upper):
        reasons.append("preferred_share")
    if filter_config.exclude_reit_infra_fund and _looks_like_reit_infra_fund(record, name_upper):
        reasons.append("reit_infra_fund")
    return list(dict.fromkeys(reasons))


def load_universe_with_fallback(providers: list[UniverseProvider]) -> tuple[list[UniverseRecord], list[str]]:
    warnings: list[str] = []
    load_universe_with_fallback.last_filter_summary = {}
    for provider in providers:
        try:
            records = provider.load()
        except Exception as exc:
            warnings.append(f"universe_provider_failed:{provider.name}:{_stable_error(exc)}")
            continue
        summary = dict(getattr(provider, "last_filter_summary", {}) or {})
        if summary.get("counts") or summary.get("samples") or summary.get("allowlist_overrides"):
            load_universe_with_fallback.last_filter_summary = summary
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
                str(filter_config.exclude_non_numeric_ticker),
                str(filter_config.exclude_spac),
                str(filter_config.exclude_preferred_share),
                str(filter_config.exclude_reit_infra_fund),
                ",".join(sorted(_normalize_ticker(ticker) for ticker in filter_config.allowlist)),
                str(filter_config.max_universe_size),
            ]
        ).encode("utf-8")
    ).hexdigest()[:16]
    return Path(cache_dir).expanduser() / f"universe_{provider_name}_{key}.json"


def _records_to_payload(records: list[UniverseRecord], *, provider: str, filter_summary: dict | None = None) -> dict:
    return {
        "cache_schema_version": UNIVERSE_CACHE_SCHEMA_VERSION,
        "cache_written_at": datetime.now().isoformat(),
        "provider": provider,
        "records": [record.to_payload() for record in records],
        "filter_summary": filter_summary or {},
    }


def _normalize_ticker(ticker: object) -> str:
    return str(ticker).strip().zfill(6)


def _looks_like_etf(record: UniverseRecord, name_upper: str) -> bool:
    kind = str(record.metadata.get("kind", "")).upper()
    return kind == "ETF" or "ETF" in name_upper or name_upper.startswith(("KODEX", "TIGER", "ACE", "KBSTAR", "HANARO", "ARIRANG", "SOL "))


def _looks_like_etn(record: UniverseRecord, name_upper: str) -> bool:
    kind = str(record.metadata.get("kind", "")).upper()
    return kind == "ETN" or "ETN" in name_upper


def _looks_like_spac(record: UniverseRecord, name_upper: str) -> bool:
    del record
    return "스팩" in name_upper or "SPAC" in name_upper or "기업인수목적" in name_upper


def _looks_like_preferred_share(record: UniverseRecord, name_upper: str) -> bool:
    del record
    return name_upper.endswith("우") or name_upper.endswith("우B") or "우선주" in name_upper


def _looks_like_reit_infra_fund(record: UniverseRecord, name_upper: str) -> bool:
    name = record.name.strip().upper()
    if "리츠" in name and not name.startswith("메리츠"):
        return True
    fund_markers = ["REIT", "인프라", "INFRA", "펀드", "FUND"]
    return any(marker in name for marker in fund_markers)


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
    return sanitize_error_message(exc).splitlines()[0][:120]
