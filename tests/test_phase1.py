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
    apply_universe_filter_result,
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
    CandidateReviewNote,
    FundamentalRecord,
    MacroStatus,
    PortfolioState,
    RecommendationAction,
    TechnicalRecord,
)
from src.main import (
    _apply_financial_data,
    _build_portfolio_source,
    _count_exclusion_reasons,
    _resolve_market_universe,
    _send_telegram_report,
)
from src.reporting import render_markdown_report, render_telegram_markdown_v2
from src.review_notes import build_candidate_review_note
from src.utils.atomic import atomic_write_json
from src.utils.config import load_settings


class Phase1Tests(unittest.TestCase):
    def test_atomic_write_json_persists_complete_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            atomic_write_json(path, {"positions": {"005930": {"quantity": 10}}})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["positions"]["005930"]["quantity"], 10)

    def test_spreadsheet_example_declares_real_provider_auth_cache_and_bounded_universe(self) -> None:
        settings = load_settings(Path(__file__).resolve().parents[1] / "config" / "settings.spreadsheet.example.yaml")

        self.assertEqual(settings["market_data"]["mode"], "real")
        self.assertEqual(settings["market_data"]["universe"], [])
        self.assertTrue(settings["market_data"]["universe_provider"]["enabled"])
        self.assertGreater(settings["market_data"]["universe_provider"]["max_universe_size"], 0)
        self.assertEqual(settings["market_data"]["cache_dir"], "data/market_cache")
        self.assertGreater(settings["market_data"]["request_delay_seconds"], 0)
        self.assertEqual(settings["financial_data"]["provider"], "opendart")
        self.assertEqual(settings["financial_data"]["dart_api_key_env"], "AUTOSTOCK_DART_API_KEY")
        self.assertEqual(settings["financial_data"]["reprt_code"], "11011")
        self.assertIn("official_api", settings["source_risk_policy"]["allowed"])
        self.assertFalse(settings["market_data"]["cross_check"]["enabled"])

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

    def test_dart_financial_provider_records_status_013_as_provider_failure(self) -> None:
        universe = [UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00")]

        class FakeResponse:
            def json(self) -> dict:
                return {"status": "013", "message": "조회된 데이터가 없습니다."}

        result = DartFinancialProvider(
            api_key="key",
            corp_code_mapping={"005930": "00126380"},
            api_get=lambda *args, **kwargs: FakeResponse(),
        ).load_for_universe(universe, market_metrics={"005930": {"per": 9.0}})

        self.assertEqual(result.fundamentals, [])
        self.assertEqual(result.exclusions["005930"], ["provider_failed:opendart:dart_status:013"])

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

    def test_apply_financial_data_marks_every_resolved_ticker_when_dart_key_missing(self) -> None:
        bundle = MarketDataBundle(
            fundamentals=[],
            technicals={},
            macro=load_unavailable_macro(),
            provider="pykrx",
            current_prices={},
            market_metrics={},
        )
        universe = [
            UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("000660", "SK하이닉스", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
        ]

        _apply_financial_data({"financial_data": {"provider": "opendart", "dart_api_key": ""}}, "real", universe, bundle)

        self.assertEqual(bundle.fundamentals, [])
        self.assertEqual(bundle.exclusion_reasons["005930"], ["dart_api_key_missing"])
        self.assertEqual(bundle.exclusion_reasons["000660"], ["dart_api_key_missing"])
        self.assertIn("dart_api_key_missing", bundle.stale_warnings)

    def test_apply_financial_data_records_dart_status_013_as_provider_failure_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "market_cache"
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
            settings = {
                "market_data": {"cache_dir": str(cache_dir)},
                "financial_data": {"provider": "opendart", "dart_api_key": "key"},
            }
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
                    return {"status": "013", "message": "조회된 데이터가 없습니다."}

            with patch("src.collectors.dart.requests.get", return_value=FakeResponse()):
                _apply_financial_data(settings, "real", universe, bundle)

        expected_reason = "provider_failed:opendart:dart_status:013"
        self.assertEqual(bundle.fundamentals, [])
        self.assertEqual(bundle.exclusion_reasons["005930"], [expected_reason])
        self.assertEqual(_count_exclusion_reasons(bundle.exclusion_reasons), {expected_reason: 1})

    def test_apply_financial_data_fetches_each_resolved_universe_record_with_configured_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "market_cache"
            cache_dir.mkdir(parents=True)
            atomic_write_json(
                cache_dir / "opendart_corp_codes.json",
                {
                    "cache_schema_version": 1,
                    "cache_written_at": datetime.now().isoformat(),
                    "source": "opendart_corp_code",
                    "source_risk": "official_api",
                    "mapping": {"005930": "00126380", "000660": "00164779"},
                },
            )
            settings = {
                "market_data": {
                    "cache_dir": str(cache_dir),
                    "freshness": {"fundamental_max_age_days": 90},
                },
                "financial_data": {
                    "provider": "opendart",
                    "dart_api_key": "key",
                    "bsns_year": "2024",
                    "reprt_code": "11014",
                },
            }
            bundle = MarketDataBundle(
                fundamentals=[],
                technicals={},
                macro=load_unavailable_macro(),
                provider="pykrx",
                current_prices={},
                market_metrics={"005930": {"per": 9.0}, "000660": {"per": 9.0}},
            )
            universe = [
                UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
                UniverseRecord("000660", "SK하이닉스", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            ]
            calls: list[dict] = []

            class FakeResponse:
                def json(self) -> dict:
                    return {"status": "000", "list": _dart_rows()}

            def fake_get(*args, **kwargs) -> FakeResponse:
                calls.append(dict(kwargs["params"]))
                return FakeResponse()

            with patch("src.collectors.dart.requests.get", side_effect=fake_get):
                _apply_financial_data(settings, "real", universe, bundle)

        self.assertEqual({record.ticker for record in bundle.fundamentals}, {"005930", "000660"})
        self.assertEqual({call["corp_code"] for call in calls}, {"00126380", "00164779"})
        self.assertTrue(all(call["bsns_year"] == "2024" for call in calls))
        self.assertTrue(all(call["reprt_code"] == "11014" for call in calls))

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

    def test_universe_filter_result_excludes_analysis_impossible_instruments(self) -> None:
        records = [
            UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("0004Y0", "디비금융제14호스팩", "KOSDAQ", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("123456", "미래에셋비전스팩", "KOSDAQ", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("005935", "삼성전자우", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("088260", "이리츠코크렙", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("078930", "GS", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
        ]

        result = apply_universe_filter_result(records, UniverseFilter())

        self.assertEqual([record.ticker for record in result.records], ["005930", "078930"])
        self.assertEqual(result.exclusion_counts["non_numeric_ticker"], 1)
        self.assertEqual(result.exclusion_counts["spac"], 2)
        self.assertEqual(result.exclusion_counts["preferred_share"], 1)
        self.assertEqual(result.exclusion_counts["reit_infra_fund"], 1)
        self.assertEqual(apply_universe_filter(records, UniverseFilter()), result.records)
        self.assertEqual(result.exclusion_samples[0]["ticker"], "0004Y0")

    def test_universe_filter_allowlist_restores_otherwise_excluded_ticker(self) -> None:
        records = [
            UniverseRecord("0004Y0", "디비금융제14호스팩", "KOSDAQ", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("123456", "미래에셋비전스팩", "KOSDAQ", "fixture", "package_public_source", "2026-06-01T00:00:00"),
        ]

        result = apply_universe_filter_result(records, UniverseFilter(allowlist=("0004Y0",)))

        self.assertEqual([record.ticker for record in result.records], ["0004Y0"])
        self.assertEqual(result.exclusion_counts, {"spac": 1})
        self.assertEqual(result.allowlist_overrides["non_numeric_ticker"], 1)
        self.assertEqual(result.allowlist_overrides["spac"], 1)

    def test_universe_filter_excludes_reit_infra_fund_without_meritz_false_positive(self) -> None:
        records = [
            UniverseRecord("138040", "메리츠금융지주", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("088980", "맥쿼리인프라", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("123789", "공모펀드", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
        ]

        result = apply_universe_filter_result(records, UniverseFilter())

        self.assertEqual([record.ticker for record in result.records], ["138040"])
        self.assertEqual(result.exclusion_counts["reit_infra_fund"], 2)

    def test_universe_filter_computes_exclusions_before_max_universe_size(self) -> None:
        records = [
            UniverseRecord("0004Y0", "디비금융제14호스팩", "KOSDAQ", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("005930", "삼성전자", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
            UniverseRecord("035420", "NAVER", "KOSPI", "fixture", "package_public_source", "2026-06-01T00:00:00"),
        ]

        result = apply_universe_filter_result(records, UniverseFilter(max_universe_size=1))

        self.assertEqual([record.ticker for record in result.records], ["005930"])
        self.assertEqual(result.exclusion_counts["non_numeric_ticker"], 1)

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

    def test_universe_cache_key_includes_filter_policy_and_allowlist(self) -> None:
        default_path = universe_cache_path("/tmp/cache", "static", UniverseFilter())
        allowlist_path = universe_cache_path("/tmp/cache", "static", UniverseFilter(allowlist=("0004Y0",)))
        disabled_path = universe_cache_path("/tmp/cache", "static", UniverseFilter(exclude_spac=False))

        self.assertNotEqual(default_path, allowlist_path)
        self.assertNotEqual(default_path, disabled_path)

    def test_cached_universe_provider_preserves_filter_summary_on_hit(self) -> None:
        class StaticUniverseProvider:
            name = "static"

            def load(self) -> list[UniverseRecord]:
                return [
                    UniverseRecord("005930", "삼성전자", "KOSPI", self.name, "package_public_source", "2026-06-01T00:00:00"),
                    UniverseRecord("0004Y0", "디비금융제14호스팩", "KOSDAQ", self.name, "package_public_source", "2026-06-01T00:00:00"),
                ]

        with tempfile.TemporaryDirectory() as tmp:
            cache_path = universe_cache_path(tmp, "static", UniverseFilter())
            provider = CachedUniverseProvider(StaticUniverseProvider(), cache_path, max_age_days=7)
            provider.load()
            provider.load()

        self.assertEqual(provider.last_filter_summary["counts"]["non_numeric_ticker"], 1)
        self.assertEqual(provider.last_filter_summary["samples"][0]["ticker"], "0004Y0")


    def test_universe_fallback_preserves_filter_summary_when_all_records_are_excluded(self) -> None:
        class AllExcludedUniverseProvider:
            def __init__(self) -> None:
                self.name = "all_excluded"
                self.filter_config = UniverseFilter()

            def load(self) -> list[UniverseRecord]:
                result = apply_universe_filter_result(
                    [
                        UniverseRecord("0004Y0", "디비금융제14호스팩", "KOSDAQ", self.name, "package_public_source", "2026-06-01T00:00:00"),
                    ],
                    self.filter_config,
                )
                self.last_filter_summary = result.summary()
                return result.records

        records, warnings = load_universe_with_fallback([AllExcludedUniverseProvider()])

        self.assertEqual(records, [])
        self.assertIn("universe_provider_empty:all_excluded", warnings)
        self.assertEqual(load_universe_with_fallback.last_filter_summary["counts"]["non_numeric_ticker"], 1)
        self.assertEqual(load_universe_with_fallback.last_filter_summary["counts"]["spac"], 1)

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

    def test_real_mode_universe_snapshot_includes_pre_universe_exclusions(self) -> None:
        class StaticUniverseProvider:
            def __init__(self, filter_config: UniverseFilter) -> None:
                self.filter_config = filter_config
                self.name = "static_universe"

            def load(self) -> list[UniverseRecord]:
                result = apply_universe_filter_result(
                    [
                        UniverseRecord("005930", "삼성전자", "KOSPI", self.name, "package_public_source", "2026-06-01T00:00:00"),
                        UniverseRecord("0004Y0", "디비금융제14호스팩", "KOSDAQ", self.name, "package_public_source", "2026-06-01T00:00:00"),
                    ],
                    self.filter_config,
                )
                self.last_filter_summary = result.summary()
                return result.records

        settings = {"market_data": {"universe": [], "universe_provider": {"markets": ["KOSPI", "KOSDAQ"]}}}
        with patch("src.main.PykrxUniverseProvider", StaticUniverseProvider), patch("src.main.FdrUniverseProvider", StaticUniverseProvider):
            tickers, records, warnings, snapshot = _resolve_market_universe(settings, "real")

        self.assertEqual(tickers, ["005930"])
        self.assertEqual(snapshot["pre_universe_exclusions"]["counts"]["non_numeric_ticker"], 1)
        self.assertEqual(snapshot["pre_universe_exclusions"]["samples"][0]["ticker"], "0004Y0")

    def test_real_mode_universe_snapshot_preserves_pre_universe_exclusions_when_all_filtered(self) -> None:
        class AllExcludedUniverseProvider:
            def __init__(self, filter_config: UniverseFilter) -> None:
                self.filter_config = filter_config
                self.name = "all_excluded"

            def load(self) -> list[UniverseRecord]:
                result = apply_universe_filter_result(
                    [
                        UniverseRecord("0004Y0", "디비금융제14호스팩", "KOSDAQ", self.name, "package_public_source", "2026-06-01T00:00:00"),
                    ],
                    self.filter_config,
                )
                self.last_filter_summary = result.summary()
                return result.records

        settings = {"market_data": {"universe": [], "universe_provider": {"markets": ["KOSPI", "KOSDAQ"]}}}
        with patch("src.main.PykrxUniverseProvider", AllExcludedUniverseProvider), patch("src.main.FdrUniverseProvider", AllExcludedUniverseProvider):
            tickers, records, warnings, snapshot = _resolve_market_universe(settings, "real")

        self.assertEqual(tickers, [])
        self.assertEqual(records, [])
        self.assertIn("universe_empty", warnings)
        self.assertEqual(snapshot["pre_universe_exclusions"]["counts"]["non_numeric_ticker"], 1)

    def test_configured_universe_bypasses_provider_conservative_filter(self) -> None:
        settings = {
            "market_data": {
                "mode": "real",
                "universe": ["0004Y0"],
                "universe_provider": {"markets": ["KOSPI", "KOSDAQ"]},
            }
        }

        tickers, records, warnings, snapshot = _resolve_market_universe(settings, "real")

        self.assertEqual(tickers, ["0004Y0"])
        self.assertEqual(records[0].source, "settings")
        self.assertEqual(warnings, [])
        self.assertNotIn("pre_universe_exclusions", snapshot)

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
        self.assertIn("다음 확인: 주요 제외 사유 상위 항목", report)
        self.assertNotIn("추가 매수 +", report)
        self.assertNotIn("목표 비중", report)

    def test_report_shows_pre_universe_exclusions_without_mixing_candidate_counts(self) -> None:
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
            candidate_exclusion_counts={"missing_peg_inputs": 2},
            universe_snapshot={
                "pre_universe_exclusions": {
                    "counts": {"non_numeric_ticker": 1},
                    "samples": [{"ticker": "0004Y0", "name": "디비금융제14호스팩", "reason": "non_numeric_ticker"}],
                }
            },
        )

        self.assertIn("주요 제외 사유", report)
        self.assertIn("missing_peg_inputs: 2개", report)
        self.assertIn("유니버스 사전 제외", report)
        self.assertIn("non_numeric_ticker: 1개", report)
        self.assertIn("0004Y0 디비금융제14호스팩", report)

    def test_report_shows_pre_universe_exclusions_when_candidates_exist(self) -> None:
        portfolio = PortfolioState(
            updated_at=datetime(2026, 6, 1),
            total_krw_evaluation=1_000_000,
            total_krw_deposit=0,
        )
        candidate = Candidate(
            ticker="005930",
            name="삼성전자",
            peg=0.5,
            strategy_type="WEEKLY_20MA_PULLBACK",
            current_price=50_000,
            final_rank=1,
        )

        report = render_markdown_report(
            generated_at=datetime(2026, 6, 1),
            macro_status=MacroStatus.CAUTION,
            macro_indicators={"kospi_above_10ma": False, "kosdaq_above_10ma": False},
            ranked_candidates=[candidate],
            trade_guides=[],
            portfolio=portfolio,
            universe_snapshot={
                "pre_universe_exclusions": {
                    "counts": {"spac": 1},
                    "samples": [{"ticker": "0004Y0", "name": "디비금융제14호스팩", "reason": "spac"}],
                }
            },
        )

        self.assertIn("1. 삼성전자 (005930)", report)
        self.assertIn("유니버스 사전 제외", report)
        self.assertIn("spac: 1개", report)

    def test_candidate_review_note_builder_records_pass_and_warning_context(self) -> None:
        candidate = Candidate(
            ticker="005930",
            name="삼성전자",
            peg=0.5,
            strategy_type="WEEKLY_20MA_PULLBACK",
            current_price=50_000,
            final_rank=1,
            review_score=170.0,
            score_inputs={"score_policy_version": "peg_macro_v1", "macro_status": "CAUTION"},
            rationale=["financial_cutoff_passed", "WEEKLY_20MA_PULLBACK"],
            risks=["macro_caution_penalty"],
            provider="fixture_realistic",
            data_provenance={"price_source": "fixture_realistic", "field_provenance": {"peg": {"source_risk": "official_api"}}},
        )

        note = build_candidate_review_note(
            candidate,
            macro_status=MacroStatus.CAUTION,
            macro_provider="unavailable",
            generated_at=datetime(2026, 6, 1, 9, 0, 0),
            market_data_warnings=["macro_data_unavailable:fixture_realistic"],
        )

        self.assertIn("재무 기준을 통과했습니다", note.review_reason)
        self.assertIn("주봉 20주선 눌림목", note.review_reason)
        self.assertIn("검토 점수 170.00", note.review_reason)
        self.assertIn("거시 환경이 CAUTION 상태", note.defer_or_reject_reason)
        self.assertIn("macro_data_unavailable:fixture_realistic", note.defer_or_reject_reason)
        self.assertIn("CAUTION 감점", note.next_check)
        self.assertIn("추가 확인", note.data_confidence)
        self.assertEqual(note.source_context["note_scope"], "ranked_candidate_only")
        self.assertEqual(note.source_context["macro_provider"], "unavailable")
        self.assertEqual(note.source_context["score_inputs"]["score_policy_version"], "peg_macro_v1")
        self.assertEqual(note.excluded_or_near_miss_context, "first_pass_uses_top_exclusion_categories_only")

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

    def test_report_renders_structured_candidate_review_note(self) -> None:
        candidate = Candidate(
            ticker="005930",
            name="삼성전자",
            peg=0.4,
            strategy_type="WEEKLY_20MA_PULLBACK",
            current_price=50_000,
            final_rank=1,
            review_score=250.0,
            review_note=CandidateReviewNote(
                review_reason="재무 기준을 통과했고 주봉 눌림목 조건을 확인했습니다.",
                defer_or_reject_reason="현재 후보 메모 기준의 즉시 보류 사유는 감지되지 않았습니다.",
                next_check="다음 거래일 전 주봉 눌림목 조건 유지 여부를 확인하세요.",
                data_confidence="기본 확인: 현재 provider/provenance 기준에서 주요 데이터 경고는 감지되지 않았습니다.",
                source_context={"provider": "fixture_realistic"},
                generated_context={"note_policy_version": "candidate_review_note_v1"},
            ),
        )
        portfolio = PortfolioState(
            updated_at=datetime(2026, 5, 27),
            total_krw_evaluation=10_000_000,
            total_krw_deposit=10_000_000,
        )

        report = render_markdown_report(
            generated_at=datetime(2026, 5, 27),
            macro_status=MacroStatus.NORMAL,
            macro_indicators={"kospi_above_10ma": True, "kosdaq_above_10ma": True},
            ranked_candidates=[candidate],
            trade_guides=[],
            portfolio=portfolio,
        )

        self.assertIn("후보 검토 [WEEKLY_20MA_PULLBACK]", report)
        self.assertIn("검토 이유: 재무 기준을 통과", report)
        self.assertIn("보류/확인 사유: 현재 후보 메모 기준", report)
        self.assertIn("다음 확인: 다음 거래일 전", report)
        self.assertIn("데이터 신뢰도: 기본 확인", report)
        self.assertNotIn("자동 주문", report)
        self.assertNotIn("목표 비중", report)
        self.assertNotIn("리밸런싱", report)

    def test_telegram_markdown_v2_escapes_review_note_text(self) -> None:
        candidate = Candidate(
            ticker="005930",
            name="삼성전자",
            peg=0.4,
            strategy_type="WEEKLY_20MA_PULLBACK",
            current_price=50_000,
            final_rank=1,
            review_note=CandidateReviewNote(
                review_reason="provider_a [확인] (주의)",
                defer_or_reject_reason="보류 없음",
                next_check="조건_유지 확인",
                data_confidence="정상",
            ),
        )
        portfolio = PortfolioState(
            updated_at=datetime(2026, 5, 27),
            total_krw_evaluation=10_000_000,
            total_krw_deposit=10_000_000,
        )
        report = render_markdown_report(
            generated_at=datetime(2026, 5, 27),
            macro_status=MacroStatus.NORMAL,
            macro_indicators={"kospi_above_10ma": True, "kosdaq_above_10ma": True},
            ranked_candidates=[candidate],
            trade_guides=[],
            portfolio=portfolio,
        )

        telegram_markdown = render_telegram_markdown_v2(report)

        self.assertIn(r"provider\_a \[확인\] \(주의\)", telegram_markdown)
        self.assertIn(r"조건\_유지 확인", telegram_markdown)

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

    def test_changed_source_has_no_debug_leaks_or_current_stage_order_language(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        changed_source = "\n".join(
            [
                (repo_root / "src" / "main.py").read_text(encoding="utf-8"),
                (repo_root / "src" / "reporting.py").read_text(encoding="utf-8"),
            ]
        )
        rendered_output_source = (repo_root / "src" / "reporting.py").read_text(encoding="utf-8")

        forbidden_fragments = [
            "print(api_key)",
            "print(candidate)",
            "매수 수량",
            "목표 비중",
            "자동 주문",
            "리밸런싱",
            "주문 실행",
        ]
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, changed_source)

        forbidden_output_secret_terms = [
            "bot_token",
            "chat_id",
            "spreadsheet_id",
            "credentials_path",
            "token_path",
        ]
        for fragment in forbidden_output_secret_terms:
            self.assertNotIn(fragment, rendered_output_source)

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
            self.assertIsNotNone(explain["items"][0]["review_note"])
            self.assertEqual(explain["items"][0]["review_note"]["source_context"]["note_scope"], "ranked_candidate_only")
            self.assertEqual(explain["items"][0]["review_note"]["source_context"]["macro_status"], "NORMAL")
            self.assertEqual(
                explain["items"][0]["review_note"]["excluded_or_near_miss_context"],
                "first_pass_uses_top_exclusion_categories_only",
            )
            report_payload = json.loads(report_files[0].read_text(encoding="utf-8"))
            self.assertEqual(report_payload["telegram_delivery_status"], "disabled")
            self.assertIn("포트폴리오 점검 요약", report_payload["markdown"])
            self.assertEqual(report_payload["review_notes"][0]["ticker"], "005930")
            self.assertIn("review_reason", report_payload["review_notes"][0]["review_note"])
            self.assertIn("검토 이유", report_payload["markdown"])

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
            self.assertIsNotNone(explain["items"][0]["review_note"])
            self.assertEqual(explain["items"][0]["review_note"]["source_context"]["macro_status"], "CAUTION")
            self.assertIn("CAUTION", explain["items"][0]["review_note"]["next_check"])
            self.assertIn("macro_data_unavailable:fixture_realistic", explain["items"][0]["review_note"]["source_context"]["risks"])

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

    def test_cli_excludes_source_disagreement_before_ranking(self) -> None:
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
                        "exclusion_reasons": {"005930": ["source_disagreement_price"]},
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
            self.assertNotIn("1. 삼성전자", completed.stdout)
            self.assertIn("source_disagreement_price: 1개", completed.stdout)
            explain = json.loads(explain_files[0].read_text(encoding="utf-8"))
            self.assertIsNone(explain["items"][0]["final_rank"])
            self.assertEqual(explain["exclusion_counts"]["source_disagreement_price"], 1)
            self.assertIn("source_disagreement_price", explain["items"][0]["risks"])


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
