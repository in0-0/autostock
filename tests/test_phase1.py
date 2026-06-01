from __future__ import annotations

import json
import zipfile
import contextlib
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.collectors.dart import DartFinancialCache, DartFinancialProvider, parse_corp_code_zip, normalize_dart_fundamental
from src.collectors.google_sheets import READONLY_SCOPE, GoogleSheetsConfig, GoogleSheetsPortfolioSource, parse_portfolio_rows
from src.collectors.market_data import (
    CachedMarketDataProvider,
    DailyPriceRow,
    FinanceDataReaderMarketDataProvider,
    FixtureMarketDataProvider,
    MarketDataBundle,
    ProviderTelemetry,
    PykrxMarketDataProvider,
    SampleMarketDataProvider,
    apply_price_source_cross_check,
    build_market_data_providers,
    candidate_completeness_warnings,
    load_market_data_with_fallback,
    load_unavailable_macro,
    market_data_warning_messages,
    _daily_price_rows,
    _normalize_daily_ohlcv,
)
from src.collectors.universe import (
    CachedUniverseProvider,
    UniverseFilter,
    UniverseRecord,
    apply_universe_filter,
    load_universe_with_fallback,
    universe_cache_path,
)
from src.collectors.portfolio_source import (
    PortfolioSourcePosition,
    PortfolioSourceResult,
    PortfolioSourceSnapshot,
    merge_portfolio_sources,
)
from src.engines.fundamental import FundamentalEngine
from src.engines.macro import MacroEngine
from src.engines.portfolio import PortfolioEngine
from src.models import (
    Candidate,
    FundamentalRecord,
    MacroStatus,
    PortfolioState,
    RecommendationAction,
    TechnicalRecord,
)
from src.main import _apply_financial_data, _build_portfolio_source, _resolve_market_universe, _send_telegram_report
from src.reporting import render_markdown_report
from src.utils.atomic import atomic_write_json


class Phase1Tests(unittest.TestCase):
    def test_atomic_write_json_persists_complete_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            atomic_write_json(path, {"positions": {"005930": {"quantity": 10}}})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["positions"]["005930"]["quantity"], 10)

    def test_fundamental_engine_uses_industry_cutoff_and_turnaround_block(self) -> None:
        settings = {
            "roe_3y_avg_min": 0.10,
            "debt_ratio_max": 1.50,
            "max_growth_divergence": 0.30,
            "min_operating_margin": {"DEFAULT": 0.08, "SOFTWARE": 0.15},
        }
        records = [
            FundamentalRecord(
                ticker="035420",
                name="NAVER",
                industry="SOFTWARE",
                roe_3y_avg=0.12,
                debt_ratio=0.4,
                operating_margin=0.14,
                net_income_growth=0.10,
                operating_income_growth=0.11,
                previous_net_income=100,
                current_net_income=110,
                peg=0.8,
            ),
            FundamentalRecord(
                ticker="000001",
                name="턴어라운드",
                industry="DEFAULT",
                roe_3y_avg=0.20,
                debt_ratio=0.4,
                operating_margin=0.20,
                net_income_growth=0.10,
                operating_income_growth=0.11,
                previous_net_income=-100,
                current_net_income=10,
                peg=0.3,
            ),
        ]
        passed, explain = FundamentalEngine(settings).evaluate(records)
        self.assertEqual(passed, [])
        self.assertFalse(explain[0]["financial_cutoff"]["operating_margin_passed"])
        self.assertTrue(explain[1]["financial_cutoff"]["is_turnaround"])

    def test_partial_success_blocks_new_buys(self) -> None:
        portfolio = PortfolioState(
            updated_at=datetime.now(),
            total_krw_evaluation=10_000_000,
            total_krw_deposit=10_000_000,
            partial_success=True,
        )
        candidate = Candidate(
            ticker="005930",
            name="삼성전자",
            peg=0.4,
            strategy_type="WEEKLY_20MA_PULLBACK",
            current_price=50_000,
        )
        guides = PortfolioEngine(1, 10, 0.20).build_trade_guides([candidate], portfolio, MacroStatus.NORMAL)
        self.assertEqual(guides[0].action, RecommendationAction.SKIP)

    def test_google_sheet_rows_parse_rich_korean_headers(self) -> None:
        rows = [
            [
                "기준일",
                "증권사",
                "계좌유형",
                "시장",
                "종목코드",
                "종목명",
                "티커",
                "자산군",
                "섹터",
                "통화",
                "보유수량",
                "평균매수가",
                "현재가",
                "평가금액",
                "전체 포트폴리오 비중",
                "메모",
            ],
            [
                "",
                "샘플증권",
                "연금저축",
                "KOSPI",
                "069500",
                "KODEX 200",
                "KRX:069500",
                "국내주식",
                "상위200",
                "KRW",
                "51",
                "72,034",
                "130600",
                "6,660,600",
                "11.01%",
                "",
            ],
            [
                "",
                "샘플증권",
                "연금저축",
                "KOSPI",
                "360750",
                "TIGER 미국S&P500",
                "KRX:360750",
                "국내주식",
                "미국 상위 500",
                "KRW",
                "454",
                "19,047",
                "28020",
                "12,721,080",
                "21.03%",
                "",
            ],
        ]

        result = parse_portfolio_rows(rows)
        portfolio = merge_portfolio_sources(result, now=datetime(2026, 5, 27))

        self.assertEqual(result.warnings, [])
        self.assertEqual(portfolio.positions["069500"].quantity, 51)
        self.assertEqual(portfolio.positions["069500"].weighted_average_price, 72034)
        self.assertEqual(portfolio.positions["360750"].market_value, 12_721_080)

    def test_google_sheet_parse_warnings_are_source_warnings_not_broker_failures(self) -> None:
        rows = [
            ["종목코드", "종목명", "보유수량", "평균매수가", "현재가"],
            ["005930", "삼성전자", "10", "70000", "80000"],
            ["", "이름없는행", "3", "1000", "1200"],
        ]

        result = parse_portfolio_rows(rows)
        portfolio = merge_portfolio_sources(result, now=datetime(2026, 5, 27))

        self.assertEqual(result.failed_sources, [])
        self.assertEqual(portfolio.failed_brokers, [])
        self.assertEqual(portfolio.failed_sources, [])
        self.assertEqual(portfolio.source_warnings, ["row_3:missing_ticker"])
        self.assertFalse(portfolio.partial_success)

    def test_google_sheet_invalid_number_warning_does_not_leak_cell_value(self) -> None:
        sensitive_value = "secret-account-123"
        rows = [
            ["종목코드", "종목명", "보유수량", "평균매수가", "현재가"],
            ["005930", "삼성전자", sensitive_value, "70000", "80000"],
        ]

        result = parse_portfolio_rows(rows)

        self.assertEqual(result.warnings, ["row_2:invalid_quantity"])
        self.assertNotIn(sensitive_value, " ".join(result.warnings))

    def test_google_sheet_non_finite_number_warning_uses_stable_code(self) -> None:
        rows = [
            ["종목코드", "종목명", "보유수량", "평균매수가", "현재가"],
            ["005930", "삼성전자", "inf", "70000", "80000"],
        ]

        result = parse_portfolio_rows(rows)

        self.assertEqual(result.warnings, ["row_2:invalid_quantity"])

    def test_portfolio_source_result_contract_merges_source_fields(self) -> None:
        result = PortfolioSourceResult(
            snapshots=[
                PortfolioSourceSnapshot(
                    source_name="spreadsheet",
                    source_type="google_sheets",
                    cash=250_000,
                    account_label="redacted_label",
                    positions=[
                        PortfolioSourcePosition(
                            ticker="005930",
                            stock_name="삼성전자",
                            quantity=2,
                            average_price=70_000,
                            current_price=80_000,
                            market_value=160_000,
                            metadata={"sector": "반도체"},
                        )
                    ],
                )
            ],
            failed_sources=["source_timeout"],
            warnings=["row_4:invalid_quantity"],
            source_type="google_sheets",
            telemetry={"rows_read": 4},
        )

        portfolio = merge_portfolio_sources(result, now=datetime(2026, 5, 27))

        self.assertTrue(result.partial_success)
        self.assertEqual(result.telemetry["rows_read"], 4)
        self.assertEqual(portfolio.failed_sources, ["source_timeout"])
        self.assertEqual(portfolio.source_warnings, ["row_4:invalid_quantity"])
        self.assertEqual(portfolio.positions["005930"].market_value, 160_000)
        self.assertEqual(portfolio.positions["005930"].metadata["sector"], "반도체")
        self.assertEqual(portfolio.total_krw_evaluation, 410_000)

    def test_google_sheets_client_uses_readonly_values_get(self) -> None:
        fake_service = FakeSheetsService(values=[["종목코드", "종목명", "보유수량", "평균매수가", "현재가"]])
        source = GoogleSheetsPortfolioSource(
            GoogleSheetsConfig(spreadsheet_id="sheet-id", range_name="Portfolio!A:E"),
            service=fake_service,
        )

        source.fetch()

        self.assertEqual(fake_service.calls, [("get", "sheet-id", "Portfolio!A:E")])
        self.assertEqual(READONLY_SCOPE, "https://www.googleapis.com/auth/spreadsheets.readonly")

    def test_google_sheets_config_allows_local_environment_overrides(self) -> None:
        settings = {
            "portfolio_source": {
                "type": "google_sheets",
                "google_sheets": {
                    "spreadsheet_id": "",
                    "range": "Portfolio!A:AF",
                    "credentials_path": "",
                    "token_path": "",
                },
            }
        }
        with patch.dict(
            "os.environ",
            {
                "AUTOSTOCK_GOOGLE_SPREADSHEET_ID": "local-sheet-id",
                "AUTOSTOCK_GOOGLE_CREDENTIALS_PATH": "config/google-service-account.local.json",
            },
        ):
            source = _build_portfolio_source(settings)

        self.assertIsInstance(source, GoogleSheetsPortfolioSource)
        self.assertEqual(source.config.spreadsheet_id, "local-sheet-id")
        self.assertEqual(source.config.credentials_path, "config/google-service-account.local.json")

    def test_unknown_portfolio_source_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported portfolio_source.type"):
            _build_portfolio_source({"portfolio_source": {"type": "typo"}})

    def test_market_data_fallback_records_failed_provider(self) -> None:
        bundle = load_market_data_with_fallback([FailingProvider(), SampleMarketDataProvider()])

        self.assertEqual(bundle.provider, "sample")
        self.assertFalse(bundle.telemetry[0].success)
        self.assertEqual(bundle.telemetry[0].provider, "failing")
        self.assertIn("market_provider_failed:failing:offline", market_data_warning_messages(bundle))

    def test_market_data_fallback_redacts_sensitive_provider_errors(self) -> None:
        bundle = load_market_data_with_fallback([SensitiveFailingProvider()])
        warnings = " ".join(market_data_warning_messages(bundle))

        self.assertIn("[path]", warnings)
        self.assertIn("[url]", warnings)
        self.assertIn("token=[redacted]", warnings)
        self.assertIn("password=[redacted]", warnings)
        self.assertIn("api_key=[redacted]", warnings)
        self.assertIn("spreadsheet_id=[redacted]", warnings)
        self.assertIn("account_id=[redacted]", warnings)
        self.assertNotIn("/Users/inyong", warnings)
        self.assertNotIn("config/google-service-account.local.json", warnings)
        self.assertNotIn("https://example.com/private", warnings)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz0123456789", warnings)
        self.assertNotIn("hunter2", warnings)
        self.assertNotIn("sk-test", warnings)
        self.assertNotIn("abc123", warnings)

    def test_market_data_provider_cache_reuses_successful_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "market.json"
            first = CachedMarketDataProvider(SampleMarketDataProvider(), cache_path).load()
            second = CachedMarketDataProvider(FailingProvider(), cache_path).load()

        self.assertEqual(first.provider, "sample")
        self.assertEqual(second.provider, "sample")
        self.assertIn("failing_cache", [entry.provider for entry in second.telemetry])

    def test_market_data_provider_cache_ignores_stale_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "market.json"
            CachedMarketDataProvider(SampleMarketDataProvider(), cache_path).load()
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            payload["cache_written_at"] = (datetime.now() - timedelta(days=3)).isoformat()
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(RuntimeError):
                CachedMarketDataProvider(FailingProvider(), cache_path, max_age_days=1).load()

    def test_market_data_provider_cache_ignores_malformed_fresh_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "market.json"
            cache_path.write_text(
                json.dumps({"cache_written_at": datetime.now().isoformat(), "technicals": {"005930": {}}}),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                CachedMarketDataProvider(FailingProvider(), cache_path, max_age_days=1).load()

    def test_market_data_provider_cache_ignores_legacy_unversioned_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "market.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "cache_written_at": datetime.now().isoformat(),
                        "fundamentals": [],
                        "technicals": {},
                        "macro": load_unavailable_macro(),
                        "provider": "legacy",
                        "current_prices": {},
                        "telemetry": [],
                        "stale_warnings": [],
                        "macro_provider": "unavailable",
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                CachedMarketDataProvider(FailingProvider(), cache_path, max_age_days=1).load()

    def test_market_data_provider_cache_ignores_bundle_without_macro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "market.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "cache_written_at": datetime.now().isoformat(),
                        "fundamentals": [
                            FundamentalRecord(
                                ticker="005930",
                                name="삼성전자",
                                industry="MANUFACTURING",
                                roe_3y_avg=0.12,
                                debt_ratio=0.31,
                                operating_margin=0.11,
                                net_income_growth=0.18,
                                operating_income_growth=0.16,
                                previous_net_income=10000,
                                current_net_income=11800,
                                peg=0.42,
                            ).model_dump()
                        ],
                        "technicals": {
                            "005930": TechnicalRecord(
                                ticker="005930",
                                monthly_close=[100.0] * 20,
                                weekly_close=[100.0] * 20,
                                weekly_volume=[1000.0] * 20,
                                listed_weeks=1000,
                            ).model_dump()
                        },
                        "provider": "fixture_realistic",
                        "current_prices": {"005930": 80000},
                        "telemetry": [],
                        "stale_warnings": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                CachedMarketDataProvider(FailingProvider(), cache_path, max_age_days=1).load()

    def test_fixture_market_data_without_macro_is_marked_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture_path = Path(tmp) / "market.json"
            fixture_path.write_text(
                json.dumps(
                    {
                        "provider": "fixture_realistic",
                        "fundamentals": [
                            FundamentalRecord(
                                ticker="005930",
                                name="삼성전자",
                                industry="MANUFACTURING",
                                roe_3y_avg=0.12,
                                debt_ratio=0.31,
                                operating_margin=0.11,
                                net_income_growth=0.18,
                                operating_income_growth=0.16,
                                previous_net_income=10000,
                                current_net_income=11800,
                                peg=0.42,
                            ).model_dump()
                        ],
                        "technicals": {
                            "005930": TechnicalRecord(
                                ticker="005930",
                                monthly_close=[100.0] * 20,
                                weekly_close=[100.0] * 20,
                                weekly_volume=[1000.0] * 20,
                                listed_weeks=1000,
                            ).model_dump()
                        },
                        "current_prices": {"005930": 80000},
                    }
                ),
                encoding="utf-8",
            )

            bundle = FixtureMarketDataProvider(fixture_path).load()

        self.assertEqual(bundle.macro_provider, "unavailable")
        self.assertEqual(bundle.macro, load_unavailable_macro())
        self.assertIn("macro_data_unavailable:fixture_realistic", bundle.stale_warnings)



    def test_dart_corp_code_zip_maps_stock_code_to_corp_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "corp.zip"
            xml = """
            <result>
              <list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name><stock_code>005930</stock_code></list>
              <list><corp_code>empty</corp_code><corp_name>비상장</corp_name><stock_code></stock_code></list>
            </result>
            """.encode("utf-8")
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("CORPCODE.xml", xml)

            mapping = parse_corp_code_zip(zip_path.read_bytes())

        self.assertEqual(mapping["005930"], "00126380")
        self.assertNotIn("", mapping)

    def test_dart_financial_normalization_produces_fundamental_with_provenance(self) -> None:
        rows = _dart_rows()

        record, exclusions = normalize_dart_fundamental(
            ticker="005930",
            name="삼성전자",
            rows=rows,
            per=9.0,
            collected_at="2026-06-01T00:00:00",
            period="2025",
        )

        self.assertEqual(exclusions, [])
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.source, "opendart")
        self.assertEqual(record.source_risk, "official_api")
        self.assertEqual(record.period, "2025")
        self.assertAlmostEqual(record.operating_margin, 0.10)
        self.assertAlmostEqual(record.debt_ratio, 0.5)
        self.assertAlmostEqual(record.net_income_growth, 0.20)
        self.assertAlmostEqual(record.peg, 0.36)
        self.assertIn("per", record.field_provenance)

    def test_dart_financial_normalization_excludes_missing_required_inputs(self) -> None:
        rows = [row for row in _dart_rows() if row["account_nm"] != "영업이익"]

        record, exclusions = normalize_dart_fundamental(
            ticker="005930",
            name="삼성전자",
            rows=rows,
            per=9.0,
            collected_at="2026-06-01T00:00:00",
            period="2025",
        )

        self.assertIsNone(record)
        self.assertIn("missing_operating_profit", exclusions)
        self.assertIn("missing_operating_income_growth_inputs", exclusions)

    def test_dart_financial_provider_missing_api_key_is_warning_not_crash(self) -> None:
        universe = [UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00")]

        result = DartFinancialProvider(api_key="").load_for_universe(universe)

        self.assertEqual(result.fundamentals, [])
        self.assertEqual(result.exclusions["005930"], ["dart_api_key_missing"])
        self.assertIn("dart_api_key_missing", result.warnings)

    def test_dart_financial_cache_reuses_rows_without_refetching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = DartFinancialCache(tmp)
            calls = 0

            def fetcher() -> list[dict]:
                nonlocal calls
                calls += 1
                return _dart_rows()

            first = cache.load_or_fetch(corp_code="00126380", bsns_year="2025", reprt_code="11011", fetcher=fetcher)
            second = cache.load_or_fetch(
                corp_code="00126380",
                bsns_year="2025",
                reprt_code="11011",
                fetcher=lambda: self.fail("fresh financial cache should avoid live refetch"),
            )

        self.assertEqual(first, second)
        self.assertEqual(calls, 1)
        self.assertEqual(cache.last_cache_status, "hit")


    def test_apply_financial_data_uses_default_cache_dir_for_corp_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            settings = {"app": {"data_dir": str(data_dir)}, "financial_data": {"provider": "opendart", "dart_api_key": "key"}}
            cache_dir = data_dir / "market_cache"
            cache_dir.mkdir(parents=True)
            atomic_write_json(
                cache_dir / "opendart_corp_codes.json",
                {
                    "cache_schema_version": 1,
                    "cache_written_at": datetime.now().isoformat(),
                    "source": "opendart_corp_code",
                    "source_risk": "official_api",
                    "mapping": {"005930": "00126380"},
                },
            )
            bundle = MarketDataBundle(
                fundamentals=[],
                technicals={},
                macro=load_unavailable_macro(),
                provider="pykrx",
                current_prices={},
                market_metrics={"005930": {"per": 9.0}},
            )
            universe = [UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00")]

            class FakeResponse:
                def json(self) -> dict:
                    return {"status": "000", "list": _dart_rows()}

            with patch("src.collectors.dart.requests.get", return_value=FakeResponse()):
                _apply_financial_data(settings, "real", universe, bundle)

        self.assertEqual(len(bundle.fundamentals), 1)
        self.assertEqual(bundle.fundamentals[0].source, "opendart")

    def test_dart_financial_provider_requires_peg_inputs(self) -> None:
        universe = [UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00")]

        class FakeResponse:
            def json(self) -> dict:
                return {"status": "000", "list": _dart_rows()}

        result = DartFinancialProvider(
            api_key="key",
            corp_code_mapping={"005930": "00126380"},
            api_get=lambda *args, **kwargs: FakeResponse(),
        ).load_for_universe(universe, market_metrics={})

        self.assertEqual(result.fundamentals, [])
        self.assertIn("missing_peg_inputs", result.exclusions["005930"])

    def test_universe_filter_excludes_etf_etn_and_limits_deterministically(self) -> None:
        records = [
            UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("069500", "KODEX 200", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("500001", "신한 ETN", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("123456", "코넥스기업", "KONEX", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("035420", "NAVER", "KOSDAQ", "fixture", "package_public_source", "2026-06-01T00:00:00"),
        ]

        filtered = apply_universe_filter(records, UniverseFilter(max_universe_size=1))

        self.assertEqual([record.ticker for record in filtered], ["035420"])

    def test_universe_fallback_records_empty_and_failed_providers(self) -> None:
        class EmptyUniverseProvider:
            name = "empty"

            def load(self) -> list[UniverseRecord]:
                return []

        class FailingUniverseProvider:
            name = "failing"

            def load(self) -> list[UniverseRecord]:
                raise RuntimeError("offline")

        records, warnings = load_universe_with_fallback([FailingUniverseProvider(), EmptyUniverseProvider()])

        self.assertEqual(records, [])
        self.assertIn("universe_provider_failed:failing:offline", warnings)
        self.assertIn("universe_provider_empty:empty", warnings)
        self.assertIn("universe_empty", warnings)

    def test_universe_provider_failure_messages_are_sanitized(self) -> None:
        class FailingUniverseProvider:
            name = "failing"

            def load(self) -> list[UniverseRecord]:
                raise RuntimeError("token=secret password=hunter2 https://example.com/private")

        records, warnings = load_universe_with_fallback([FailingUniverseProvider()])

        self.assertEqual(records, [])
        joined = " ".join(warnings)
        self.assertIn("token=[redacted]", joined)
        self.assertIn("password=[redacted]", joined)
        self.assertIn("[url]", joined)
        self.assertNotIn("secret", joined)
        self.assertNotIn("hunter2", joined)

    def test_cached_universe_provider_uses_fresh_cache_and_records_schema(self) -> None:
        class StaticUniverseProvider:
            name = "static"

            def load(self) -> list[UniverseRecord]:
                return [UniverseRecord("005930", "삼성전자", "KOSPI", self.name, "package_public_source", "2026-06-01T00:00:00")]

        with tempfile.TemporaryDirectory() as tmp:
            cache_path = universe_cache_path(tmp, "static", UniverseFilter())
            provider = CachedUniverseProvider(StaticUniverseProvider(), cache_path, max_age_days=7)
            first = provider.load()
            second = provider.load()
            payload = json.loads(cache_path.read_text(encoding="utf-8"))

        self.assertEqual(first, second)
        self.assertEqual(provider.last_cache_status, "hit")
        self.assertEqual(payload["cache_schema_version"], 1)
        self.assertEqual(payload["records"][0]["source_risk"], "package_public_source")


    def test_real_mode_empty_config_universe_resolves_from_provider(self) -> None:
        class StaticUniverseProvider:
            def __init__(self, filter_config: UniverseFilter) -> None:
                self.filter_config = filter_config
                self.name = "static_universe"

            def load(self) -> list[UniverseRecord]:
                return apply_universe_filter(
                    [
                        UniverseRecord("005930", "삼성전자", "KOSPI", self.name, "package_public_source", "2026-06-01T00:00:00"),
                        UniverseRecord("069500", "KODEX 200", "KOSPI", self.name, "package_public_source", "2026-06-01T00:00:00"),
                    ],
                    self.filter_config,
                )

        settings = {"market_data": {"universe": [], "universe_provider": {"markets": ["KOSPI"], "max_universe_size": 1}}}
        with patch("src.main.PykrxUniverseProvider", StaticUniverseProvider), patch("src.main.FdrUniverseProvider", StaticUniverseProvider):
            tickers, records, warnings, snapshot = _resolve_market_universe(settings, "real")

        self.assertEqual(tickers, ["005930"])
        self.assertEqual(records[0].name, "삼성전자")
        self.assertEqual(warnings, [])
        self.assertEqual(snapshot["count"], 1)

    def test_report_shows_top_exclusion_counts_when_no_candidates(self) -> None:
        portfolio = PortfolioState(
            updated_at=datetime(2026, 6, 1),
            total_krw_evaluation=1_000_000,
            total_krw_deposit=0,
        )

        report = render_markdown_report(
            generated_at=datetime(2026, 6, 1),
            macro_status=MacroStatus.CAUTION,
            macro_indicators={"kospi_above_10ma": False, "kosdaq_above_10ma": False},
            ranked_candidates=[],
            trade_guides=[],
            portfolio=portfolio,
            candidate_exclusion_counts={"missing_peg_inputs": 2, "dart_api_key_missing": 1},
        )

        self.assertIn("주요 제외 사유", report)
        self.assertIn("missing_peg_inputs: 2개", report)
        self.assertNotIn("추가 매수 +", report)
        self.assertNotIn("목표 비중", report)

    def test_real_market_data_mode_does_not_fall_back_to_sample(self) -> None:
        providers = build_market_data_providers("real", universe=[])
        bundle = load_market_data_with_fallback(providers)

        self.assertEqual([provider.name for provider in providers], ["pykrx", "fdr", "naver"])
        self.assertEqual(bundle.provider, "none")
        self.assertIn("all_market_data_providers_failed", bundle.stale_warnings)
        self.assertEqual(bundle.macro_provider, "unavailable")
        self.assertEqual(bundle.macro, load_unavailable_macro())

    def test_unknown_market_data_mode_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported market_data.mode"):
            build_market_data_providers("typo")

    def test_real_provider_success_marks_macro_unavailable_not_sample(self) -> None:
        for provider in [
            PykrxMarketDataProvider(universe=["005930"]),
            FinanceDataReaderMarketDataProvider(universe=["005930"]),
        ]:
            name_patch = (
                patch.object(provider, "_ticker_name", return_value="005930")
                if hasattr(provider, "_ticker_name")
                else contextlib.nullcontext()
            )
            with patch.object(provider, "_load_price_rows", return_value=_daily_rows(90)), name_patch:
                bundle = provider.load()

            self.assertEqual(bundle.macro_provider, "unavailable")
            self.assertEqual(bundle.macro, load_unavailable_macro())
            self.assertEqual(bundle.fundamentals, [])
            self.assertTrue(any(warning.startswith("macro_data_unavailable") for warning in bundle.stale_warnings))
            self.assertFalse(any(warning.startswith("missing_full_fundamental_fields") for warning in bundle.stale_warnings))

    def test_daily_ohlcv_normalization_uses_calendar_week_and_month_buckets(self) -> None:
        rows = [
            DailyPriceRow(date(2026, 1, 29), 100.0, 10.0),
            DailyPriceRow(date(2026, 1, 30), 101.0, 20.0),
            DailyPriceRow(date(2026, 2, 2), 102.0, 30.0),
            DailyPriceRow(date(2026, 2, 4), 103.0, 40.0),
            DailyPriceRow(date(2026, 2, 5), 104.0, 50.0),
            DailyPriceRow(date(2026, 2, 10), 105.0, 60.0),
            DailyPriceRow(date(2026, 3, 2), 106.0, 70.0),
        ]

        normalized = _normalize_daily_ohlcv(rows)

        self.assertEqual(normalized.monthly_close, [101.0, 105.0, 106.0])
        self.assertEqual(normalized.weekly_close, [101.0, 104.0, 105.0, 106.0])
        self.assertEqual(normalized.weekly_volume, [30.0, 120.0, 60.0, 70.0])
        self.assertEqual(normalized.listed_weeks, 4)

    def test_provider_daily_price_rows_require_date_index(self) -> None:
        frame = FakeFrame(
            rows={
                "Close": [100.0, 101.0],
                "Volume": [1000.0, 1100.0],
            },
            index=["2026-01-02", "2026-01-05"],
        )

        with self.assertRaisesRegex(ValueError, "market_data_provider_missing_date_index"):
            _daily_price_rows(frame, ["Close"], ["Volume"])

    def test_provider_daily_price_rows_preserve_index_alignment_with_missing_values(self) -> None:
        frame = FakeFrame(
            rows={
                "Close": [100.0, None, 102.0],
                "Volume": [1000.0, 1100.0, 1200.0],
            },
            index=[date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        )

        rows = _daily_price_rows(frame, ["Close"], ["Volume"])

        self.assertEqual(
            rows,
            [
                DailyPriceRow(date(2026, 1, 2), 100.0, 1000.0),
                DailyPriceRow(date(2026, 1, 6), 102.0, 1200.0),
            ],
        )

    def test_real_provider_paths_resample_daily_rows_before_building_technical_record(self) -> None:
        rows = [
            DailyPriceRow(date(2026, 1, 29), 100.0, 10.0),
            DailyPriceRow(date(2026, 1, 30), 101.0, 20.0),
            DailyPriceRow(date(2026, 2, 2), 102.0, 30.0),
            DailyPriceRow(date(2026, 2, 4), 103.0, 40.0),
            DailyPriceRow(date(2026, 2, 5), 104.0, 50.0),
            DailyPriceRow(date(2026, 2, 10), 105.0, 60.0),
            DailyPriceRow(date(2026, 3, 2), 106.0, 70.0),
        ]
        for provider in [
            PykrxMarketDataProvider(universe=["005930"]),
            FinanceDataReaderMarketDataProvider(universe=["005930"]),
        ]:
            name_patch = (
                patch.object(provider, "_ticker_name", return_value="005930")
                if hasattr(provider, "_ticker_name")
                else contextlib.nullcontext()
            )
            with patch.object(provider, "_load_price_rows", return_value=rows), name_patch:
                bundle = provider.load()

            technical = bundle.technicals["005930"]
            self.assertEqual(technical.monthly_close, [101.0, 105.0, 106.0])
            self.assertEqual(technical.weekly_close, [101.0, 104.0, 105.0, 106.0])
            self.assertEqual(technical.weekly_volume, [30.0, 120.0, 60.0, 70.0])
            self.assertEqual(technical.listed_weeks, 4)
            self.assertEqual(bundle.current_prices["005930"], 106)

    def test_candidate_completeness_blocks_missing_current_price(self) -> None:
        fundamental = FundamentalRecord(
            ticker="005930",
            name="삼성전자",
            roe_3y_avg=0.12,
            debt_ratio=0.31,
            operating_margin=0.11,
            net_income_growth=0.18,
            operating_income_growth=0.16,
            previous_net_income=10_000,
            current_net_income=11_800,
            peg=0.42,
        )
        technical = TechnicalRecord(
            ticker="005930",
            monthly_close=[100.0] * 20,
            weekly_close=[100.0] * 20,
            weekly_volume=[100.0] * 20,
            listed_weeks=120,
        )

        warnings = candidate_completeness_warnings(fundamental, technical, None, provider="sample")

        self.assertIn("missing_current_price", warnings)

    def test_candidate_completeness_blocks_provider_stale_or_missing_field_warnings(self) -> None:
        fundamental = FundamentalRecord(
            ticker="005930",
            name="삼성전자",
            roe_3y_avg=0.12,
            debt_ratio=0.31,
            operating_margin=0.11,
            net_income_growth=0.18,
            operating_income_growth=0.16,
            previous_net_income=10_000,
            current_net_income=11_800,
            peg=0.42,
        )
        technical = TechnicalRecord(
            ticker="005930",
            monthly_close=[100.0] * 20,
            weekly_close=[100.0] * 20,
            weekly_volume=[100.0] * 20,
            listed_weeks=120,
        )

        warnings = candidate_completeness_warnings(
            fundamental,
            technical,
            50_000,
            provider="pykrx",
            provider_warnings=["missing_full_fundamental_fields:pykrx"],
        )

        self.assertIn("provider_warning:missing_full_fundamental_fields:pykrx", warnings)

    def test_candidate_completeness_keeps_macro_unavailable_as_context(self) -> None:
        fundamental = FundamentalRecord(
            ticker="005930",
            name="삼성전자",
            roe_3y_avg=0.12,
            debt_ratio=0.31,
            operating_margin=0.11,
            net_income_growth=0.18,
            operating_income_growth=0.16,
            previous_net_income=10_000,
            current_net_income=11_800,
            peg=0.42,
        )
        technical = TechnicalRecord(
            ticker="005930",
            monthly_close=[100.0] * 20,
            weekly_close=[100.0] * 20,
            weekly_volume=[100.0] * 20,
            listed_weeks=120,
        )

        warnings = candidate_completeness_warnings(
            fundamental,
            technical,
            50_000,
            provider="fixture_realistic",
            provider_warnings=["macro_data_unavailable:fixture_realistic"],
        )

        self.assertNotIn("provider_warning:macro_data_unavailable:fixture_realistic", warnings)

    def test_candidate_completeness_blocks_stale_price_data(self) -> None:
        fundamental = FundamentalRecord(
            ticker="005930",
            name="삼성전자",
            roe_3y_avg=0.12,
            debt_ratio=0.31,
            operating_margin=0.11,
            net_income_growth=0.18,
            operating_income_growth=0.16,
            previous_net_income=10_000,
            current_net_income=11_800,
            peg=0.42,
        )
        technical = TechnicalRecord(
            ticker="005930",
            monthly_close=[100.0] * 20,
            weekly_close=[100.0] * 20,
            weekly_volume=[100.0] * 20,
            listed_weeks=120,
        )

        warnings = candidate_completeness_warnings(
            fundamental,
            technical,
            50_000,
            provider="pykrx",
            latest_trade_date=(date.today() - timedelta(days=10)).isoformat(),
            price_max_age_days=3,
        )

        self.assertIn("stale_price_data", warnings)

    def test_candidate_completeness_blocks_missing_real_price_trade_date(self) -> None:
        fundamental = FundamentalRecord(
            ticker="005930",
            name="삼성전자",
            roe_3y_avg=0.12,
            debt_ratio=0.31,
            operating_margin=0.11,
            net_income_growth=0.18,
            operating_income_growth=0.16,
            previous_net_income=10_000,
            current_net_income=11_800,
            peg=0.42,
        )
        technical = TechnicalRecord(
            ticker="005930",
            monthly_close=[100.0] * 20,
            weekly_close=[100.0] * 20,
            weekly_volume=[100.0] * 20,
            listed_weeks=120,
        )

        warnings = candidate_completeness_warnings(
            fundamental,
            technical,
            50_000,
            provider="pykrx",
            latest_trade_date=None,
            price_max_age_days=3,
        )

        self.assertIn("stale_price_data", warnings)

    def test_candidate_completeness_blocks_disallowed_source_risk(self) -> None:
        fundamental = FundamentalRecord(
            ticker="005930",
            name="삼성전자",
            roe_3y_avg=0.12,
            debt_ratio=0.31,
            operating_margin=0.11,
            net_income_growth=0.18,
            operating_income_growth=0.16,
            previous_net_income=10_000,
            current_net_income=11_800,
            peg=0.42,
            source_risk="crawler_snapshot",
        )
        technical = TechnicalRecord(
            ticker="005930",
            monthly_close=[100.0] * 20,
            weekly_close=[100.0] * 20,
            weekly_volume=[100.0] * 20,
            listed_weeks=120,
        )

        warnings = candidate_completeness_warnings(
            fundamental,
            technical,
            50_000,
            provider="crawler",
            allowed_source_risks={"official_api"},
        )

        self.assertIn("source_risk_blocked", warnings)

    def test_candidate_completeness_blocks_disallowed_universe_or_price_source_risk(self) -> None:
        fundamental = FundamentalRecord(
            ticker="005930",
            name="삼성전자",
            roe_3y_avg=0.12,
            debt_ratio=0.31,
            operating_margin=0.11,
            net_income_growth=0.18,
            operating_income_growth=0.16,
            previous_net_income=10_000,
            current_net_income=11_800,
            peg=0.42,
            source_risk="official_api",
        )
        technical = TechnicalRecord(
            ticker="005930",
            monthly_close=[100.0] * 20,
            weekly_close=[100.0] * 20,
            weekly_volume=[100.0] * 20,
            listed_weeks=120,
        )

        warnings = candidate_completeness_warnings(
            fundamental,
            technical,
            50_000,
            provider="pykrx",
            allowed_source_risks={"official_api"},
            source_risks=["package_public_source"],
        )

        self.assertIn("source_risk_blocked", warnings)

    def test_price_source_disagreement_excludes_when_cross_check_enabled(self) -> None:
        primary = MarketDataBundle(
            fundamentals=[],
            technicals={},
            macro=load_unavailable_macro(),
            provider="pykrx",
            current_prices={"005930": 100_000, "000660": 50_000},
            telemetry=[ProviderTelemetry("pykrx", True)],
        )
        cross_check = MarketDataBundle(
            fundamentals=[],
            technicals={},
            macro=load_unavailable_macro(),
            provider="fdr",
            current_prices={"005930": 90_000, "000660": 49_500},
            telemetry=[ProviderTelemetry("fdr", True)],
        )

        apply_price_source_cross_check(primary, cross_check, max_disagreement_ratio=0.03)

        self.assertEqual(primary.exclusion_reasons["005930"], ["source_disagreement_price"])
        self.assertNotIn("000660", primary.exclusion_reasons)

    def test_macro_unavailable_is_caution_not_risk_off(self) -> None:
        status, indicators = MacroEngine().evaluate(load_unavailable_macro())

        self.assertEqual(status, MacroStatus.CAUTION)
        self.assertTrue(indicators["macro_data_unavailable"])

    def test_partial_macro_payload_is_caution_context(self) -> None:
        status, indicators = MacroEngine().evaluate({"kospi_monthly_close": [2500] * 12})

        self.assertEqual(status, MacroStatus.CAUTION)
        self.assertTrue(indicators["macro_data_unavailable"])

    def test_candidate_ranking_records_score_inputs_and_caution_penalty(self) -> None:
        candidate = Candidate(
            ticker="005930",
            name="삼성전자",
            peg=0.5,
            strategy_type="WEEKLY_20MA_PULLBACK",
            current_price=50_000,
        )

        ranked = PortfolioEngine(1, 10, 0.20).rank_candidates([candidate], MacroStatus.CAUTION)

        self.assertEqual(ranked[0].final_rank, 1)
        self.assertEqual(ranked[0].review_score, 170.0)
        self.assertEqual(ranked[0].score_inputs["score_policy_version"], "peg_macro_v1")
        self.assertEqual(ranked[0].score_inputs["macro_status"], "CAUTION")
        self.assertEqual(ranked[0].score_inputs["macro_penalty"], 0.85)
        self.assertIn("macro_caution_penalty", ranked[0].risks)

    def test_telegram_delivery_status_disabled_sent_and_failed_are_sanitized(self) -> None:
        self.assertEqual(_send_telegram_report("report", {"telegram": {"bot_token": "", "chat_id": ""}}), "disabled")
        self.assertEqual(
            _send_telegram_report(
                "report",
                {"telegram": {"bot_token": "REPLACE_WITH_LOCAL_TELEGRAM_BOT_TOKEN", "chat_id": "REPLACE_WITH_LOCAL_TELEGRAM_CHAT_ID"}},
            ),
            "disabled",
        )

        with patch("src.main.TelegramClient") as client_class:
            client_class.return_value.send_message.return_value = None
            status = _send_telegram_report("A_B (report)", {"telegram": {"bot_token": "safe-token", "chat_id": "safe-chat"}})

        self.assertEqual(status, "sent")
        client_class.return_value.send_message.assert_called_once_with(r"A\_B \(report\)")

        with patch("src.main.TelegramClient") as client_class:
            client_class.return_value.send_message.side_effect = RuntimeError(
                "https://api.telegram.org/botsecret/sendMessage token=secret chat_id=1234567890123456789012345"
            )
            status = _send_telegram_report("report", {"telegram": {"bot_token": "safe-token", "chat_id": "safe-chat"}})

        self.assertTrue(status.startswith("failed:"))
        self.assertIn("[url]", status)
        self.assertIn("token=[redacted]", status)
        self.assertIn("chat_id=[redacted]", status)
        self.assertNotIn("botsecret", status)

        with patch("src.main.TelegramClient") as client_class:
            client_class.return_value.send_message.side_effect = RuntimeError(
                "{'chat_id': '123456789', \"token\": \"shortsecret\", 'password': 'hunter2'}"
            )
            status = _send_telegram_report("report", {"telegram": {"bot_token": "safe-token", "chat_id": "safe-chat"}})

        self.assertIn("chat_id=[redacted]", status)
        self.assertIn("token=[redacted]", status)
        self.assertIn("password=[redacted]", status)
        self.assertNotIn("123456789", status)
        self.assertNotIn("shortsecret", status)
        self.assertNotIn("hunter2", status)

    def test_all_market_data_provider_failures_are_visible_in_report(self) -> None:
        bundle = load_market_data_with_fallback([FailingProvider()])
        portfolio = PortfolioState(
            updated_at=datetime(2026, 5, 27),
            total_krw_evaluation=10_000_000,
            total_krw_deposit=10_000_000,
        )

        report = render_markdown_report(
            generated_at=datetime(2026, 5, 27),
            macro_status=MacroStatus.NORMAL,
            macro_indicators={"kospi_above_10ma": True, "kosdaq_above_10ma": True},
            ranked_candidates=[],
            trade_guides=[],
            portfolio=portfolio,
            market_data_warnings=market_data_warning_messages(bundle),
        )

        self.assertIn("시장데이터 경고: all_market_data_providers_failed", report)
        self.assertIn("시장데이터 경고: market_provider_failed:failing:offline", report)

    def test_report_mvp_language_avoids_share_sizing(self) -> None:
        candidate = Candidate(
            ticker="005930",
            name="삼성전자",
            peg=0.4,
            strategy_type="WEEKLY_20MA_PULLBACK",
            current_price=50_000,
            final_rank=1,
            rationale=["financial_cutoff_passed"],
            risks=["provider_fallback_used"],
            provider="sample",
        )
        portfolio = PortfolioState(
            updated_at=datetime(2026, 5, 27),
            total_krw_evaluation=10_000_000,
            total_krw_deposit=10_000_000,
        )
        guides = PortfolioEngine(1, 10, 0.20).build_trade_guides([candidate], portfolio, MacroStatus.NORMAL)

        report = render_markdown_report(
            generated_at=datetime(2026, 5, 27),
            macro_status=MacroStatus.NORMAL,
            macro_indicators={"kospi_above_10ma": True, "kosdaq_above_10ma": True},
            ranked_candidates=[candidate],
            trade_guides=guides,
            portfolio=portfolio,
        )

        self.assertIn("근거: financial_cutoff_passed", report)
        self.assertIn("리스크: provider_fallback_used", report)
        self.assertIn("후보 검토 메모", report)
        self.assertIn("우량 성장주 후보 TOP", report)
        self.assertNotIn("추천 TOP", report)
        self.assertNotIn("추가 매수 +", report)
        self.assertNotIn("매수 차단", report)
        self.assertNotIn("신규 매수", report)
        self.assertNotIn("[REDUCE]", report)
        self.assertNotIn("[SKIP]", report)

    def test_cli_with_spreadsheet_and_market_fixtures_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_fixture = root / "portfolio.csv"
            market_fixture = root / "market.json"
            settings_path = root / "settings.yaml"
            data_dir = root / "data"

            portfolio_fixture.write_text(
                "\n".join(
                    [
                        "종목코드,종목명,보유수량,평균매수가,현재가,평가금액",
                        "069500,KODEX 200,51,\"72,034\",130600,\"6,660,600\"",
                    ]
                ),
                encoding="utf-8",
            )
            market_fixture.write_text(
                json.dumps(
                    {
                        "provider": "fixture_realistic",
                        "macro": {
                            "kospi_monthly_close": [2500, 2520, 2540, 2580, 2600, 2640, 2660, 2680, 2710, 2740, 2760],
                            "kosdaq_monthly_close": [800, 810, 820, 835, 840, 850, 860, 870, 882, 895, 905],
                            "us_rate": 0.0525,
                            "yield_curve_10y2y": -0.0012,
                        },
                        "fundamentals": [
                            {
                                "ticker": "005930",
                                "name": "삼성전자",
                                "industry": "MANUFACTURING",
                                "roe_3y_avg": 0.12,
                                "debt_ratio": 0.31,
                                "operating_margin": 0.11,
                                "net_income_growth": 0.18,
                                "operating_income_growth": 0.16,
                                "previous_net_income": 10000,
                                "current_net_income": 11800,
                                "peg": 0.42,
                            }
                        ],
                        "technicals": {
                            "005930": {
                                "ticker": "005930",
                                "monthly_close": [90, 92, 94, 96, 99, 101, 104, 106, 108, 111, 114, 117, 119, 121, 124, 126, 129, 132, 134, 137, 140],
                                "weekly_close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 112],
                                "weekly_volume": [1000000, 1100000, 1050000, 980000, 800000],
                                "listed_weeks": 1000,
                            }
                        },
                        "current_prices": {"005930": 112},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings_path.write_text(
                "\n".join(
                    [
                        "app:",
                        f"  data_dir: {data_dir}",
                        "  broker_connectors: []",
                        "portfolio_source:",
                        "  type: google_sheets",
                        "  google_sheets:",
                        "    spreadsheet_id: \"\"",
                        "    range: \"Portfolio!A:AF\"",
                        f"    fixture_path: {portfolio_fixture}",
                        "market_data:",
                        "  mode: fixture",
                        f"  fixture_path: {market_fixture}",
                        "strategy:",
                        "  max_candidates: 10",
                        "  min_candidates: 1",
                        "  target_position_ratio: 0.20",
                        "  fundamental_filter:",
                        "    roe_3y_avg_min: 0.10",
                        "    debt_ratio_max: 1.50",
                        "    min_operating_margin:",
                        "      DEFAULT: 0.08",
                        "      MANUFACTURING: 0.05",
                        "    max_growth_divergence: 0.30",
                    ]
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-m", "src.main", "--settings", str(settings_path)],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            report_files = list((data_dir / "reports").glob("report_*.json"))
            explain_files = list((data_dir / "explain_logs").glob("explain_*.json"))
            self.assertTrue(report_files)
            self.assertTrue(explain_files)
            self.assertIn("삼성전자", completed.stdout)
            self.assertIn("근거:", completed.stdout)
            explain = json.loads(explain_files[0].read_text(encoding="utf-8"))
            self.assertEqual(explain["market_data_provider"], "fixture_realistic")
            self.assertEqual(explain["macro_provider"], "fixture_realistic")
            self.assertEqual(explain["items"][0]["provider"], "fixture_realistic")
            self.assertEqual(explain["items"][0]["final_rank"], 1)
            self.assertGreater(explain["items"][0]["review_score"], 0)
            self.assertEqual(explain["items"][0]["score_inputs"]["macro_status"], "NORMAL")
            self.assertEqual(explain["items"][0]["data_provenance"]["price_source"], "fixture_realistic")
            self.assertIn("field_provenance", explain["items"][0]["data_provenance"])
            self.assertEqual(explain["portfolio_source_type"], "google_sheets")
            self.assertEqual(explain["source_warnings"], [])
            self.assertEqual(explain["failed_sources"], [])
            self.assertEqual(explain["telegram_delivery_status"], "disabled")
            report_payload = json.loads(report_files[0].read_text(encoding="utf-8"))
            self.assertEqual(report_payload["telegram_delivery_status"], "disabled")
            self.assertIn("포트폴리오 점검 요약", report_payload["markdown"])

    def test_cli_with_missing_fixture_macro_keeps_candidates_with_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_fixture = root / "portfolio.csv"
            market_fixture = root / "market.json"
            settings_path = root / "settings.yaml"
            data_dir = root / "data"

            portfolio_fixture.write_text(
                "\n".join(
                    [
                        "종목코드,종목명,보유수량,평균매수가,현재가,평가금액",
                        "069500,KODEX 200,51,\"72,034\",130600,\"6,660,600\"",
                    ]
                ),
                encoding="utf-8",
            )
            market_fixture.write_text(
                json.dumps(
                    {
                        "provider": "fixture_realistic",
                        "fundamentals": [
                            {
                                "ticker": "005930",
                                "name": "삼성전자",
                                "industry": "MANUFACTURING",
                                "roe_3y_avg": 0.12,
                                "debt_ratio": 0.31,
                                "operating_margin": 0.11,
                                "net_income_growth": 0.18,
                                "operating_income_growth": 0.16,
                                "previous_net_income": 10000,
                                "current_net_income": 11800,
                                "peg": 0.42,
                            }
                        ],
                        "technicals": {
                            "005930": {
                                "ticker": "005930",
                                "monthly_close": [90, 92, 94, 96, 99, 101, 104, 106, 108, 111, 114, 117, 119, 121, 124, 126, 129, 132, 134, 137, 140],
                                "weekly_close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 112],
                                "weekly_volume": [1000000, 1100000, 1050000, 980000, 800000],
                                "listed_weeks": 1000,
                            }
                        },
                        "current_prices": {"005930": 112},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings_path.write_text(
                "\n".join(
                    [
                        "app:",
                        f"  data_dir: {data_dir}",
                        "  broker_connectors: []",
                        "portfolio_source:",
                        "  type: google_sheets",
                        "  google_sheets:",
                        "    spreadsheet_id: \"\"",
                        "    range: \"Portfolio!A:AF\"",
                        f"    fixture_path: {portfolio_fixture}",
                        "market_data:",
                        "  mode: fixture",
                        f"  fixture_path: {market_fixture}",
                        "strategy:",
                        "  max_candidates: 10",
                        "  min_candidates: 1",
                        "  target_position_ratio: 0.20",
                        "  fundamental_filter:",
                        "    roe_3y_avg_min: 0.10",
                        "    debt_ratio_max: 1.50",
                        "    min_operating_margin:",
                        "      DEFAULT: 0.08",
                        "      MANUFACTURING: 0.05",
                        "    max_growth_divergence: 0.30",
                    ]
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-m", "src.main", "--settings", str(settings_path)],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            explain_files = list((data_dir / "explain_logs").glob("explain_*.json"))
            self.assertTrue(explain_files)
            self.assertIn("CAUTION", completed.stdout)
            self.assertIn("1. 삼성전자", completed.stdout)
            self.assertIn("macro_data_unavailable:fixture_realistic", completed.stdout)
            explain = json.loads(explain_files[0].read_text(encoding="utf-8"))
            self.assertEqual(explain["macro_status"], "CAUTION")
            self.assertEqual(explain["macro_provider"], "unavailable")
            self.assertIn("macro_data_unavailable:fixture_realistic", explain["market_data_warnings"])
            self.assertEqual(explain["items"][0]["final_rank"], 1)
            self.assertEqual(explain["items"][0]["score_inputs"]["macro_status"], "CAUTION")
            self.assertEqual(explain["items"][0]["data_provenance"]["price_source"], "fixture_realistic")
            self.assertIn("macro_data_unavailable:fixture_realistic", explain["items"][0]["risks"])
            self.assertIn("macro_caution_penalty", explain["items"][0]["risks"])

    def test_cli_with_macro_risk_off_blocks_buy_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_fixture = root / "portfolio.csv"
            market_fixture = root / "market.json"
            settings_path = root / "settings.yaml"
            data_dir = root / "data"

            portfolio_fixture.write_text(
                "\n".join(
                    [
                        "종목코드,종목명,보유수량,평균매수가,현재가,평가금액",
                        "069500,KODEX 200,51,\"72,034\",130600,\"6,660,600\"",
                    ]
                ),
                encoding="utf-8",
            )
            market_fixture.write_text(
                json.dumps(
                    {
                        "provider": "fixture_realistic",
                        "macro": {
                            "kospi_monthly_close": [3000, 2990, 2980, 2970, 2960, 2950, 2940, 2930, 2920, 2910, 2900],
                            "kosdaq_monthly_close": [1000, 990, 980, 970, 960, 950, 940, 930, 920, 910, 900],
                            "us_rate": 0.0525,
                            "yield_curve_10y2y": -0.0012,
                        },
                        "fundamentals": [
                            {
                                "ticker": "005930",
                                "name": "삼성전자",
                                "industry": "MANUFACTURING",
                                "roe_3y_avg": 0.12,
                                "debt_ratio": 0.31,
                                "operating_margin": 0.11,
                                "net_income_growth": 0.18,
                                "operating_income_growth": 0.16,
                                "previous_net_income": 10000,
                                "current_net_income": 11800,
                                "peg": 0.42,
                            }
                        ],
                        "technicals": {
                            "005930": {
                                "ticker": "005930",
                                "monthly_close": [90, 92, 94, 96, 99, 101, 104, 106, 108, 111, 114, 117, 119, 121, 124, 126, 129, 132, 134, 137, 140],
                                "weekly_close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 112],
                                "weekly_volume": [1000000, 1100000, 1050000, 980000, 800000],
                                "listed_weeks": 1000,
                            }
                        },
                        "current_prices": {"005930": 112},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings_path.write_text(
                "\n".join(
                    [
                        "app:",
                        f"  data_dir: {data_dir}",
                        "  broker_connectors: []",
                        "portfolio_source:",
                        "  type: google_sheets",
                        "  google_sheets:",
                        "    spreadsheet_id: \"\"",
                        "    range: \"Portfolio!A:AF\"",
                        f"    fixture_path: {portfolio_fixture}",
                        "market_data:",
                        "  mode: fixture",
                        f"  fixture_path: {market_fixture}",
                        "strategy:",
                        "  max_candidates: 10",
                        "  min_candidates: 1",
                        "  target_position_ratio: 0.20",
                        "  fundamental_filter:",
                        "    roe_3y_avg_min: 0.10",
                        "    debt_ratio_max: 1.50",
                        "    min_operating_margin:",
                        "      DEFAULT: 0.08",
                        "      MANUFACTURING: 0.05",
                        "    max_growth_divergence: 0.30",
                    ]
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-m", "src.main", "--settings", str(settings_path)],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            explain_files = list((data_dir / "explain_logs").glob("explain_*.json"))
            self.assertTrue(explain_files)
            self.assertIn("RISK_OFF", completed.stdout)
            self.assertIn("검토 가능한 신규 후보가 없습니다.", completed.stdout)
            self.assertNotIn("1. 삼성전자", completed.stdout)
            explain = json.loads(explain_files[0].read_text(encoding="utf-8"))
            self.assertEqual(explain["macro_status"], "RISK_OFF")
            self.assertIsNone(explain["items"][0]["final_rank"])
            self.assertEqual(explain["items"][0]["data_provenance"]["price_source"], "fixture_realistic")
            self.assertIn("macro_risk_off", explain["items"][0]["risks"])

    def test_cli_reports_quality_gate_exclusion_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portfolio_fixture = root / "portfolio.csv"
            market_fixture = root / "market.json"
            settings_path = root / "settings.yaml"
            data_dir = root / "data"

            portfolio_fixture.write_text(
                "\n".join(
                    [
                        "종목코드,종목명,보유수량,평균매수가,현재가,평가금액",
                        "069500,KODEX 200,51,\"72,034\",130600,\"6,660,600\"",
                    ]
                ),
                encoding="utf-8",
            )
            market_fixture.write_text(
                json.dumps(
                    {
                        "provider": "fixture_realistic",
                        "macro": {
                            "kospi_monthly_close": [2500, 2520, 2540, 2580, 2600, 2640, 2660, 2680, 2710, 2740, 2760],
                            "kosdaq_monthly_close": [800, 810, 820, 835, 840, 850, 860, 870, 882, 895, 905],
                            "us_rate": 0.0525,
                            "yield_curve_10y2y": -0.0012,
                        },
                        "fundamentals": [
                            {
                                "ticker": "005930",
                                "name": "삼성전자",
                                "industry": "MANUFACTURING",
                                "roe_3y_avg": 0.12,
                                "debt_ratio": 0.31,
                                "operating_margin": 0.11,
                                "net_income_growth": 0.18,
                                "operating_income_growth": 0.16,
                                "previous_net_income": 10000,
                                "current_net_income": 11800,
                                "peg": 0.42,
                                "source_risk": "crawler_snapshot",
                            }
                        ],
                        "technicals": {
                            "005930": {
                                "ticker": "005930",
                                "monthly_close": [90, 92, 94, 96, 99, 101, 104, 106, 108, 111, 114, 117, 119, 121, 124, 126, 129, 132, 134, 137, 140],
                                "weekly_close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 112],
                                "weekly_volume": [1000000, 1100000, 1050000, 980000, 800000],
                                "listed_weeks": 1000,
                            }
                        },
                        "current_prices": {"005930": 112},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            settings_path.write_text(
                "\n".join(
                    [
                        "app:",
                        f"  data_dir: {data_dir}",
                        "  broker_connectors: []",
                        "portfolio_source:",
                        "  type: google_sheets",
                        "  google_sheets:",
                        "    spreadsheet_id: \"\"",
                        "    range: \"Portfolio!A:AF\"",
                        f"    fixture_path: {portfolio_fixture}",
                        "market_data:",
                        "  mode: fixture",
                        f"  fixture_path: {market_fixture}",
                        "source_risk_policy:",
                        "  allowed:",
                        "    - official_api",
                        "    - manual_config",
                        "strategy:",
                        "  max_candidates: 10",
                        "  min_candidates: 1",
                        "  target_position_ratio: 0.20",
                        "  fundamental_filter:",
                        "    roe_3y_avg_min: 0.10",
                        "    debt_ratio_max: 1.50",
                        "    min_operating_margin:",
                        "      DEFAULT: 0.08",
                        "      MANUFACTURING: 0.05",
                        "    max_growth_divergence: 0.30",
                    ]
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-m", "src.main", "--settings", str(settings_path)],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=True,
            )

            explain_files = list((data_dir / "explain_logs").glob("explain_*.json"))
            report_files = list((data_dir / "reports").glob("report_*.json"))
            self.assertTrue(explain_files)
            self.assertTrue(report_files)
            self.assertIn("source_risk_blocked: 1개", completed.stdout)
            explain = json.loads(explain_files[0].read_text(encoding="utf-8"))
            self.assertEqual(explain["exclusion_counts"]["source_risk_blocked"], 1)
            self.assertIn("source_risk_blocked", explain["items"][0]["risks"])
            report_payload = json.loads(report_files[0].read_text(encoding="utf-8"))
            self.assertIn("source_risk_blocked: 1개", report_payload["markdown"])


class FakeSheetsService:
    def __init__(self, values: list[list[str]]) -> None:
        self.response_values = values
        self.calls: list[tuple[str, str, str]] = []

    def spreadsheets(self) -> "FakeSheetsService":
        return self

    def values(self) -> "FakeSheetsService":
        return self

    def get(self, *, spreadsheetId: str, range: str) -> "FakeSheetsService":  # noqa: A002
        self.calls.append(("get", spreadsheetId, range))
        return self

    def execute(self) -> dict:
        return {"values": self.response_values}


class FakeFrame:
    def __init__(self, *, rows: dict[str, list[object]], index: list[object]) -> None:
        self.rows = rows
        self.index = index

    def __getitem__(self, name: str) -> list[object]:
        return self.rows[name]


def _daily_rows(count: int) -> list[DailyPriceRow]:
    start = date(2026, 1, 1)
    return [
        DailyPriceRow(start + timedelta(days=offset), 100.0 + offset, 1000.0 + offset)
        for offset in range(count)
    ]


class FailingProvider:
    name = "failing"

    def load(self) -> MarketDataBundle:
        raise RuntimeError("offline")


class SensitiveFailingProvider:
    name = "sensitive_failing"

    def load(self) -> MarketDataBundle:
        raise RuntimeError(
            "/Users/inyong/config/google-token.local.json "
            "token=abcdefghijklmnopqrstuvwxyz0123456789 "
            "password hunter2 "
            "api_key sk-test "
            "config/google-service-account.local.json "
            "spreadsheet_id=abc123 "
            "account_id 1234 "
            "https://example.com/private"
        )


if __name__ == "__main__":
    unittest.main()


def _dart_rows() -> list[dict[str, str]]:
    return [
        {"account_nm": "매출액", "thstrm_amount": "100,000", "frmtrm_amount": "90,000", "bfefrmtrm_amount": "80,000"},
        {"account_nm": "영업이익", "thstrm_amount": "10,000", "frmtrm_amount": "8,000", "bfefrmtrm_amount": "7,000"},
        {"account_nm": "당기순이익", "thstrm_amount": "12,000", "frmtrm_amount": "10,000", "bfefrmtrm_amount": "8,000"},
        {"account_nm": "부채총계", "thstrm_amount": "50,000", "frmtrm_amount": "48,000", "bfefrmtrm_amount": "45,000"},
        {"account_nm": "자본총계", "thstrm_amount": "100,000", "frmtrm_amount": "90,000", "bfefrmtrm_amount": "80,000"},
    ]
