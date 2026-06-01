from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from src.collectors.dart import DartCorpCodeCache, DartFinancialProvider
from src.collectors.google_sheets import GoogleSheetsConfig, GoogleSheetsPortfolioSource
from src.collectors.market_data import (
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
    _apply_financial_data(settings, market_data_mode, universe_records, market_data)
    market_warnings = market_data_warning_messages(market_data)
    macro_status, macro_indicators = MacroEngine().evaluate(market_data.macro)

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
    trade_guides = []

    ranked_by_ticker = {candidate.ticker: candidate for candidate in ranked_candidates}
    candidate_by_ticker = {candidate.ticker: candidate for candidate in candidates}
    technical_by_ticker = {item["ticker"]: item for item in technical_explain}

    explain_items = []
    exclusion_counts = _count_exclusion_reasons(market_data.exclusion_reasons)
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
                "provider": candidate.provider if candidate else market_data.provider,
                "source": getattr(candidate, "source", None),
                "macro_context": {
                    "status": macro_status.value,
                    "provider": market_data.macro_provider,
                    "indicators": macro_indicators,
                },
            }
        )
    for ticker, reasons in market_data.exclusion_reasons.items():
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
    )
    telegram_delivery_status = _send_telegram_report(report, settings)
    for ticker, reasons in market_data.exclusion_reasons.items():
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
        telegram_delivery_status=telegram_delivery_status,
        candidate_exclusion_counts=exclusion_counts,
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
    )
    date_key = now.strftime("%Y-%m-%d")
    atomic_write_json(data_dir / "explain_logs" / f"explain_{date_key}.json", explain_log.model_dump(mode="json"))
    atomic_write_json(
        data_dir / "reports" / f"report_{date_key}.json",
        {
            "generated_at": now.isoformat(),
            "markdown": report,
            "telegram_delivery_status": telegram_delivery_status,
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
    cache_dir = get_nested(settings, "market_data", "cache_dir", default="")
    if api_key and cache_dir:
        try:
            corp_cache = DartCorpCodeCache(Path(cache_dir) / "opendart_corp_codes.json", api_key)
            mapping = corp_cache.load()
            if corp_cache.last_cache_status == "stale":
                market_data.stale_warnings.append("stale_dart_corp_code_cache")
        except Exception as exc:
            market_data.stale_warnings.append(f"dart_corp_code_failed:{sanitize_error_message(exc)}")
    provider = DartFinancialProvider(api_key=api_key, corp_code_mapping=mapping)
    result = provider.load_for_universe(universe_records, market_metrics=market_data.market_metrics)
    market_data.fundamentals = result.fundamentals
    market_data.exclusion_reasons = _merge_exclusion_reasons(market_data.exclusion_reasons, result.exclusions)
    market_data.stale_warnings.extend(result.warnings)


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
