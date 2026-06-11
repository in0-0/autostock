from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from src.collectors.dart import DartCorpCodeCache, DartFinancialCache, DartFinancialProvider
from src.collectors.google_sheets import GoogleSheetsConfig, GoogleSheetsPortfolioSource
from src.collectors.market_data import (
    apply_price_source_cross_check,
    build_market_data_providers,
    candidate_completeness_warnings,
    load_market_data_with_fallback,
    market_data_warning_messages,
)
from src.collectors.portfolio_source import BrokerPortfolioSource, PortfolioSource, merge_portfolio_sources
from src.collectors.universe import (
    CachedUniverseProvider,
    FdrUniverseProvider,
    PykrxUniverseProvider,
    UniverseFilter,
    UniverseRecord,
    load_universe_with_fallback,
    universe_cache_path,
)
from src.engines.exit import ExitEngine
from src.engines.fundamental import FundamentalEngine
from src.engines.macro import MacroEngine
from src.engines.portfolio import PortfolioEngine
from src.engines.technical import TechnicalEngine
from src.models import Candidate, ExplainLog, MacroStatus
from src.reporting import render_markdown_report, render_telegram_markdown_v2
from src.review_notes import build_candidate_review_note
from src.utils.atomic import atomic_write_json
from src.utils.config import get_nested, load_settings
from src.utils.redaction import sanitize_error_message
from src.utils.telegram import TelegramClient


def run(settings_path: str) -> None:
    settings = load_settings(settings_path)
    now = datetime.now()
    data_dir = Path(get_nested(settings, "app", "data_dir", default="data"))

    portfolio_source = _build_portfolio_source(settings)
    portfolio_result = portfolio_source.fetch()
    portfolio = merge_portfolio_sources(portfolio_result, ip_changed_flag=False, now=now)
    atomic_write_json(data_dir / "portfolio_state.json", portfolio.model_dump(mode="json"))

    market_data_mode = str(get_nested(settings, "market_data", "mode", default="sample"))
    market_universe, universe_records, universe_warnings, universe_snapshot = _resolve_market_universe(settings, market_data_mode)
    lookback_days = int(get_nested(settings, "market_data", "lookback_days", default=460))
    market_fixture_path = get_nested(settings, "market_data", "fixture_path", default=None)
    request_delay_seconds = float(get_nested(settings, "market_data", "request_delay_seconds", default=0.0))
    market_cache_dir = get_nested(settings, "market_data", "cache_dir", default=None)
    cache_max_age_days = int(get_nested(settings, "market_data", "cache_max_age_days", default=1))
    market_data = load_market_data_with_fallback(
        build_market_data_providers(
            market_data_mode,
            market_universe,
            lookback_days,
            fixture_path=market_fixture_path,
            request_delay_seconds=request_delay_seconds,
            cache_dir=market_cache_dir,
            cache_max_age_days=cache_max_age_days,
        )
    )
    market_data.stale_warnings = [*universe_warnings, *market_data.stale_warnings]
    market_data.universe_snapshot = universe_snapshot
    _apply_price_cross_check(
        settings,
        market_data_mode,
        market_universe,
        lookback_days,
        request_delay_seconds,
        market_cache_dir,
        cache_max_age_days,
        market_data,
    )
    _apply_financial_data(settings, market_data_mode, universe_records, market_data)
    market_warnings = market_data_warning_messages(market_data)
    macro_status, macro_indicators = MacroEngine().evaluate(market_data.macro)

    freshness_settings = get_nested(settings, "market_data", "freshness", default={})
    price_max_age_days = int(freshness_settings.get("price_max_age_days", 3))
    source_risk_policy = get_nested(settings, "source_risk_policy", default={})
    allowed_source_risks = set(source_risk_policy.get("allowed", ["official_api", "package_public_source", "manual_config"]))

    fundamentals, fundamental_explain = FundamentalEngine(
        get_nested(settings, "strategy", "fundamental_filter", default={})
    ).evaluate(market_data.fundamentals)
    technical_passed, technical_explain = TechnicalEngine().evaluate(fundamentals, market_data.technicals)

    exit_engine = ExitEngine()
    candidates: list[Candidate] = []
    incomplete_candidate_reasons: dict[str, list[str]] = {}
    for item in technical_passed:
        fundamental = item["fundamental"]
        technical = item["technical"]
        held = portfolio.positions.get(fundamental.ticker)
        current_price = held.current_price if held else market_data.current_prices.get(fundamental.ticker)
        completeness_warnings = candidate_completeness_warnings(
            fundamental,
            technical,
            current_price,
            provider=market_data.provider,
            provider_warnings=market_warnings,
            latest_trade_date=market_data.latest_trade_dates.get(fundamental.ticker),
            price_max_age_days=price_max_age_days,
            allowed_source_risks=allowed_source_risks,
            source_risks=_candidate_source_risks(fundamental, market_data, universe_records),
        )
        completeness_warnings = list(
            dict.fromkeys(
                [
                    *market_data.exclusion_reasons.get(fundamental.ticker, []),
                    *completeness_warnings,
                ]
            )
        )
        if completeness_warnings:
            incomplete_candidate_reasons[fundamental.ticker] = completeness_warnings
            continue
        candidate = Candidate(
            ticker=fundamental.ticker,
            name=fundamental.name,
            peg=fundamental.peg,
            strategy_type=item["strategy_type"],
            current_price=current_price,
            provider=market_data.provider,
            data_provenance=_candidate_data_provenance(fundamental, market_data, universe_records),
            rationale=[
                "financial_cutoff_passed",
                item["strategy_type"],
            ],
            risks=[
                *market_warnings,
            ],
            filters={
                "financial_cutoff": next(
                    explain["financial_cutoff"] for explain in fundamental_explain if explain["ticker"] == fundamental.ticker
                ),
                "technical_pullback": next(
                    explain["technical_pullback"] for explain in technical_explain if explain["ticker"] == fundamental.ticker
                ),
            },
        )
        candidate = candidate.model_copy(update={"exit_signal": exit_engine.evaluate(candidate)})
        candidates.append(candidate)

    strategy_settings = get_nested(settings, "strategy", default={})
    portfolio_engine = PortfolioEngine(
        min_candidates=int(strategy_settings.get("min_candidates", 5)),
        max_candidates=int(strategy_settings.get("max_candidates", 10)),
        target_position_ratio=float(strategy_settings.get("target_position_ratio", 0.20)),
    )
    rankable_candidates = candidates
    if macro_status == MacroStatus.RISK_OFF:
        for candidate in candidates:
            incomplete_candidate_reasons[candidate.ticker] = [
                *incomplete_candidate_reasons.get(candidate.ticker, []),
                "macro_risk_off",
            ]
        rankable_candidates = []
    ranked_candidates = portfolio_engine.rank_candidates(rankable_candidates, macro_status)
    ranked_candidates = [
        candidate.model_copy(
            update={
                "review_note": build_candidate_review_note(
                    candidate,
                    macro_status=macro_status,
                    macro_provider=market_data.macro_provider,
                    generated_at=now,
                    market_data_warnings=market_warnings,
                )
            }
        )
        for candidate in ranked_candidates
    ]
    trade_guides = []

    ranked_by_ticker = {candidate.ticker: candidate for candidate in ranked_candidates}
    candidate_by_ticker = {candidate.ticker: candidate for candidate in candidates}
    fundamentals_by_ticker = {fundamental.ticker: fundamental for fundamental in fundamentals}
    technical_by_ticker = {item["ticker"]: item for item in technical_explain}

    all_exclusion_reasons = _merge_exclusion_reasons(market_data.exclusion_reasons, incomplete_candidate_reasons)
    explain_items = []
    exclusion_counts = _count_exclusion_reasons(all_exclusion_reasons)
    for item in fundamental_explain:
        ticker = item["ticker"]
        ranked = ranked_by_ticker.get(ticker)
        candidate = ranked_by_ticker.get(ticker) or candidate_by_ticker.get(ticker)
        risk_reasons = list(
            dict.fromkeys(
                [
                    *(candidate.risks if candidate else []),
                    *incomplete_candidate_reasons.get(ticker, []),
                ]
            )
        )
        explain_items.append(
            {
                "ticker": ticker,
                "name": item["name"],
                "filters": {
                    "financial_cutoff": item["financial_cutoff"],
                    "technical_pullback": technical_by_ticker.get(
                        ticker,
                        {"technical_pullback": {"passed": False, "reason": "not_evaluated_after_financial_filter"}},
                    )["technical_pullback"],
                },
                "final_rank": ranked.final_rank if ranked else None,
                "review_score": ranked.review_score if ranked else None,
                "score_inputs": ranked.score_inputs if ranked else {},
                "peg": item["peg"],
                "strategy_type": candidate.strategy_type if candidate else None,
                "exit_signal": candidate.exit_signal.value if candidate else None,
                "rationale": candidate.rationale if candidate else [],
                "risks": risk_reasons,
                "review_note": ranked.review_note.model_dump(mode="json") if ranked and ranked.review_note else None,
                "provider": candidate.provider if candidate else market_data.provider,
                "data_provenance": candidate.data_provenance if candidate else _fundamental_data_provenance(fundamentals_by_ticker.get(ticker), market_data, universe_records),
                "macro_context": {
                    "status": macro_status.value,
                    "provider": market_data.macro_provider,
                    "indicators": macro_indicators,
                },
            }
        )
    for ticker, reasons in all_exclusion_reasons.items():
        if any(item.get("ticker") == ticker for item in explain_items):
            continue
        explain_items.append(
            {
                "ticker": ticker,
                "name": _universe_name(universe_records, ticker),
                "filters": {},
                "final_rank": None,
                "review_score": None,
                "score_inputs": {},
                "peg": None,
                "strategy_type": None,
                "exit_signal": None,
                "rationale": [],
                "risks": list(dict.fromkeys(reasons)),
                "provider": market_data.provider,
                "data_provenance": _exclusion_data_provenance(ticker, market_data, universe_records),
                "macro_context": {
                    "status": macro_status.value,
                    "provider": market_data.macro_provider,
                    "indicators": macro_indicators,
                },
            }
        )

    report = render_markdown_report(
        generated_at=now,
        macro_status=macro_status,
        macro_indicators=macro_indicators,
        ranked_candidates=ranked_candidates,
        trade_guides=trade_guides,
        portfolio=portfolio,
        market_data_warnings=market_warnings,
        telegram_delivery_status=None,
        candidate_exclusion_counts=exclusion_counts,
        universe_snapshot=market_data.universe_snapshot,
    )
    telegram_delivery_status = _send_telegram_report(report, settings)

    report = render_markdown_report(
        generated_at=now,
        macro_status=macro_status,
        macro_indicators=macro_indicators,
        ranked_candidates=ranked_candidates,
        trade_guides=trade_guides,
        portfolio=portfolio,
        market_data_warnings=market_warnings,
        telegram_delivery_status=telegram_delivery_status,
        candidate_exclusion_counts=exclusion_counts,
        universe_snapshot=market_data.universe_snapshot,
    )
    explain_log = ExplainLog(
        generated_at=now,
        macro_status=macro_status,
        macro_indicators=macro_indicators,
        partial_success=portfolio.partial_success,
        failed_brokers=portfolio.failed_brokers,
        items=explain_items,
        failed_sources=portfolio.failed_sources,
        source_warnings=portfolio.source_warnings,
        portfolio_source_type=portfolio_result.source_type,
        market_data_provider=market_data.provider,
        macro_provider=market_data.macro_provider,
        market_data_warnings=market_warnings,
        telegram_delivery_status=telegram_delivery_status,
        exclusion_counts=exclusion_counts,
        universe_snapshot=market_data.universe_snapshot,
    )
    date_key = now.strftime("%Y-%m-%d")
    atomic_write_json(data_dir / "explain_logs" / f"explain_{date_key}.json", explain_log.model_dump(mode="json"))
    atomic_write_json(
        data_dir / "reports" / f"report_{date_key}.json",
        {
            "generated_at": now.isoformat(),
            "markdown": report,
            "telegram_delivery_status": telegram_delivery_status,
            "review_notes": [
                {
                    "ticker": candidate.ticker,
                    "name": candidate.name,
                    "final_rank": candidate.final_rank,
                    "review_note": candidate.review_note.model_dump(mode="json") if candidate.review_note else None,
                }
                for candidate in ranked_candidates
            ],
        },
    )
    print(report)


def _resolve_market_universe(settings: dict, market_data_mode: str) -> tuple[list[str], list[UniverseRecord], list[str], dict | None]:
    configured = [_normalize_ticker(ticker) for ticker in get_nested(settings, "market_data", "universe", default=[])]
    if configured or market_data_mode != "real":
        records = [
            UniverseRecord(
                ticker=ticker,
                name=ticker,
                market="CONFIG",
                source="settings",
                source_risk="manual_config",
                collected_at=datetime.now().isoformat(),
            )
            for ticker in configured
        ]
        return configured, records, [], {"source": "settings", "count": len(configured)} if configured else None

    provider_settings = get_nested(settings, "market_data", "universe_provider", default={})
    if provider_settings.get("enabled", True) is False:
        return [], [], ["universe_empty"], {"source": "disabled", "count": 0}

    markets = tuple(provider_settings.get("markets") or ["KOSPI", "KOSDAQ"])
    max_size = provider_settings.get("max_universe_size")
    filter_config = UniverseFilter(
        markets=markets,
        exclude_etf=bool(provider_settings.get("exclude_etf", True)),
        exclude_etn=bool(provider_settings.get("exclude_etn", True)),
        exclude_konex=bool(provider_settings.get("exclude_konex", True)),
        exclude_non_numeric_ticker=bool(provider_settings.get("exclude_non_numeric_ticker", True)),
        exclude_spac=bool(provider_settings.get("exclude_spac", True)),
        exclude_preferred_share=bool(provider_settings.get("exclude_preferred_share", True)),
        exclude_reit_infra_fund=bool(provider_settings.get("exclude_reit_infra_fund", True)),
        allowlist=tuple(provider_settings.get("allowlist") or ()),
        max_universe_size=int(max_size) if max_size not in (None, "") else None,
    )
    providers = [PykrxUniverseProvider(filter_config), FdrUniverseProvider(filter_config)]
    cache_dir = get_nested(settings, "market_data", "cache_dir", default="")
    if cache_dir:
        providers = [
            CachedUniverseProvider(provider, universe_cache_path(cache_dir, provider.name, filter_config), max_age_days=7)
            for provider in providers
        ]
    records, warnings = load_universe_with_fallback(providers)
    snapshot = {
        "source": records[0].source if records else "none",
        "source_risk": records[0].source_risk if records else None,
        "count": len(records),
        "markets": list(markets),
        "collected_at": records[0].collected_at if records else None,
    }
    filter_summary = getattr(load_universe_with_fallback, "last_filter_summary", {}) or {}
    if filter_summary.get("counts") or filter_summary.get("samples") or filter_summary.get("allowlist_overrides"):
        snapshot["pre_universe_exclusions"] = filter_summary
    return [record.ticker for record in records], records, warnings, snapshot


def _apply_financial_data(settings: dict, market_data_mode: str, universe_records: list[UniverseRecord], market_data) -> None:
    if market_data_mode != "real" or not universe_records:
        return
    financial_settings = get_nested(settings, "financial_data", default={})
    provider_name = str(financial_settings.get("provider", "opendart"))
    if provider_name != "opendart":
        return
    api_key = _setting_or_env(financial_settings, "dart_api_key", str(financial_settings.get("dart_api_key_env", "AUTOSTOCK_DART_API_KEY")), "")
    mapping = {}
    cache_dir = get_nested(settings, "market_data", "cache_dir", default="") or str(Path(get_nested(settings, "app", "data_dir", default="data")) / "market_cache")
    if api_key and cache_dir:
        try:
            corp_cache = DartCorpCodeCache(Path(cache_dir) / "opendart_corp_codes.json", api_key)
            mapping = corp_cache.load()
            if corp_cache.last_cache_status == "stale":
                market_data.stale_warnings.append("stale_dart_corp_code_cache")
        except Exception as exc:
            market_data.stale_warnings.append(f"dart_corp_code_failed:{sanitize_error_message(exc)}")
    financial_cache_max_age_days = int(get_nested(settings, "market_data", "freshness", "fundamental_max_age_days", default=120))
    financial_cache = (
        DartFinancialCache(cache_dir, max_age_days=financial_cache_max_age_days)
        if api_key and cache_dir
        else None
    )
    bsns_year = str(financial_settings.get("bsns_year") or "") or None
    reprt_code = str(financial_settings.get("reprt_code") or "11011")
    provider = DartFinancialProvider(
        api_key=api_key,
        corp_code_mapping=mapping,
        bsns_year=bsns_year,
        reprt_code=reprt_code,
        financial_cache=financial_cache,
    )
    result = provider.load_for_universe(universe_records, market_metrics=market_data.market_metrics)
    market_data.fundamentals = result.fundamentals
    market_data.exclusion_reasons = _merge_exclusion_reasons(market_data.exclusion_reasons, result.exclusions)
    market_data.stale_warnings.extend(result.warnings)


def _apply_price_cross_check(
    settings: dict,
    market_data_mode: str,
    market_universe: list[str],
    lookback_days: int,
    request_delay_seconds: float,
    market_cache_dir: str | None,
    cache_max_age_days: int,
    market_data,
) -> None:
    if market_data_mode != "real" or market_data.provider != "pykrx":
        return
    cross_check_settings = get_nested(settings, "market_data", "cross_check", default={})
    if not bool(cross_check_settings.get("enabled", False)):
        return
    providers = build_market_data_providers(
        "real",
        market_universe,
        lookback_days,
        request_delay_seconds=request_delay_seconds,
        cache_dir=market_cache_dir,
        cache_max_age_days=cache_max_age_days,
    )
    fdr_provider = next((provider for provider in providers if getattr(provider, "name", "") == "fdr"), None)
    if fdr_provider is None:
        return
    try:
        cross_check_bundle = fdr_provider.load()
    except Exception as exc:
        market_data.stale_warnings.append(f"price_cross_check_failed:fdr:{sanitize_error_message(exc)}")
        return
    apply_price_source_cross_check(
        market_data,
        cross_check_bundle,
        max_disagreement_ratio=float(cross_check_settings.get("max_disagreement_ratio", 0.03)),
    )


def _merge_exclusion_reasons(left: dict[str, list[str]], right: dict[str, list[str]]) -> dict[str, list[str]]:
    merged = {ticker: list(reasons) for ticker, reasons in left.items()}
    for ticker, reasons in right.items():
        merged[ticker] = list(dict.fromkeys([*merged.get(ticker, []), *reasons]))
    return merged


def _count_exclusion_reasons(exclusions: dict[str, list[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for reasons in exclusions.values():
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _universe_name(records: list[UniverseRecord], ticker: str) -> str:
    for record in records:
        if record.ticker == ticker:
            return record.name
    return ticker


def _normalize_ticker(ticker: object) -> str:
    return str(ticker).strip().zfill(6)


def _candidate_data_provenance(fundamental: object, market_data, universe_records: list[UniverseRecord]) -> dict:
    return _fundamental_data_provenance(fundamental, market_data, universe_records)


def _candidate_source_risks(fundamental: object, market_data, universe_records: list[UniverseRecord]) -> list[str]:
    ticker = str(getattr(fundamental, "ticker", ""))
    universe_record = _universe_record_for_ticker(universe_records, ticker) if ticker else None
    risks = [
        getattr(universe_record, "source_risk", None),
        _price_source_risk(market_data.provider),
        getattr(fundamental, "source_risk", None),
    ]
    return [risk for risk in dict.fromkeys(risks) if risk]


def _fundamental_data_provenance(fundamental: object, market_data, universe_records: list[UniverseRecord]) -> dict:
    ticker = str(getattr(fundamental, "ticker", ""))
    universe_record = _universe_record_for_ticker(universe_records, ticker) if ticker else None
    source_risks = [
        risk
        for risk in [
            getattr(universe_record, "source_risk", None),
            getattr(fundamental, "source_risk", None),
        ]
        if risk
    ]
    return {
        "universe": universe_record.to_payload() if universe_record else market_data.universe_snapshot,
        "price_source": market_data.provider,
        "price_source_risk": _price_source_risk(market_data.provider),
        "price_latest_trade_date": market_data.latest_trade_dates.get(ticker) if ticker else None,
        "market_metrics": market_data.market_metrics.get(ticker, {}) if ticker else {},
        "financial_source": getattr(fundamental, "source", None),
        "financial_source_risk": getattr(fundamental, "source_risk", None),
        "source_risks": list(dict.fromkeys(source_risks)),
        "financial_period": getattr(fundamental, "period", None),
        "financial_collected_at": getattr(fundamental, "collected_at", None),
        "field_provenance": getattr(fundamental, "field_provenance", {}),
    }


def _exclusion_data_provenance(ticker: str, market_data, universe_records: list[UniverseRecord]) -> dict:
    universe_record = _universe_record_for_ticker(universe_records, ticker)
    return {
        "universe": universe_record.to_payload() if universe_record else market_data.universe_snapshot,
        "price_source": market_data.provider,
        "price_source_risk": _price_source_risk(market_data.provider),
        "price_latest_trade_date": market_data.latest_trade_dates.get(ticker),
        "market_metrics": market_data.market_metrics.get(ticker, {}),
        "source_risks": [universe_record.source_risk] if universe_record and universe_record.source_risk else [],
    }


def _universe_record_for_ticker(records: list[UniverseRecord], ticker: str) -> UniverseRecord | None:
    for record in records:
        if record.ticker == ticker:
            return record
    return None


def _price_source_risk(provider: str | None) -> str | None:
    if provider in {"pykrx", "fdr"}:
        return "package_public_source"
    if provider in {"sample", "fixture", "fixture_realistic"}:
        return "manual_config"
    if provider == "opendart":
        return "official_api"
    return None


def _build_portfolio_source(settings: dict) -> PortfolioSource:
    source_type = str(get_nested(settings, "portfolio_source", "type", default="broker_mock"))
    if source_type == "google_sheets":
        google_settings = get_nested(settings, "portfolio_source", "google_sheets", default={})
        return GoogleSheetsPortfolioSource(
            GoogleSheetsConfig(
                spreadsheet_id=_setting_or_env(
                    google_settings,
                    "spreadsheet_id",
                    "AUTOSTOCK_GOOGLE_SPREADSHEET_ID",
                    "",
                ),
                range_name=_setting_or_env(
                    google_settings,
                    "range",
                    "AUTOSTOCK_GOOGLE_SHEETS_RANGE",
                    "Sheet1!A:AF",
                ),
                credentials_path=_setting_or_env(
                    google_settings,
                    "credentials_path",
                    "AUTOSTOCK_GOOGLE_CREDENTIALS_PATH",
                    "",
                ),
                token_path=_setting_or_env(
                    google_settings,
                    "token_path",
                    "AUTOSTOCK_GOOGLE_TOKEN_PATH",
                    "",
                ),
                fixture_path=google_settings.get("fixture_path"),
            )
        )
    if source_type != "broker_mock":
        raise ValueError(f"unsupported portfolio_source.type: {source_type}")
    connector_paths = get_nested(settings, "app", "broker_connectors", default=[])
    return BrokerPortfolioSource(list(connector_paths))


def _setting_or_env(settings: dict, key: str, env_name: str, default: str) -> str:
    return str(os.getenv(env_name) or settings.get(key) or default)


def _send_telegram_report(report: str, settings: dict) -> str:
    telegram_settings = get_nested(settings, "telegram", default={})
    bot_token = _telegram_setting(telegram_settings, "bot_token", "AUTOSTOCK_TELEGRAM_BOT_TOKEN")
    chat_id = _telegram_setting(telegram_settings, "chat_id", "AUTOSTOCK_TELEGRAM_CHAT_ID")
    parse_mode = str(telegram_settings.get("parse_mode") or "MarkdownV2")
    if not bot_token or not chat_id:
        return "disabled"

    client = TelegramClient(bot_token=bot_token, chat_id=chat_id, parse_mode=parse_mode)
    message = render_telegram_markdown_v2(report) if parse_mode.lower() == "markdownv2" else report
    try:
        client.send_message(message)
    except Exception as exc:
        return f"failed:{sanitize_error_message(exc)}"
    return "sent"


def _telegram_setting(settings: dict, key: str, env_name: str) -> str:
    value = str(os.getenv(env_name) or settings.get(key) or "")
    return "" if _is_placeholder_secret(value) else value


def _is_placeholder_secret(value: str) -> bool:
    normalized = value.strip().upper()
    return not normalized or normalized.startswith("REPLACE_WITH_")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", default="config/settings.yaml")
    args = parser.parse_args()
    run(args.settings)


if __name__ == "__main__":
    main()
