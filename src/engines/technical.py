from __future__ import annotations

from typing import Any

from src.models import FundamentalRecord, TechnicalRecord


class TechnicalEngine:
    def __init__(self, pullback_band: float = 0.03) -> None:
        self.pullback_band = pullback_band

    def evaluate(
        self,
        fundamentals: list[FundamentalRecord],
        technicals: dict[str, TechnicalRecord],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        passed: list[dict[str, Any]] = []
        explain_items: list[dict[str, Any]] = []

        for fundamental in fundamentals:
            technical = technicals.get(fundamental.ticker)
            if technical is None:
                explain_items.append(self._explain_missing(fundamental))
                continue

            monthly_trend_passed = self._monthly_uptrend(technical.monthly_close)
            listed_period_passed = technical.listed_weeks >= 104
            weekly_20ma = self._moving_average(technical.weekly_close, 20)
            weekly_60ma = self._moving_average(technical.weekly_close, 60)
            latest_close = technical.weekly_close[-1]
            disparity_20ma = self._disparity(latest_close, weekly_20ma)
            disparity_60ma = self._disparity(latest_close, weekly_60ma)
            volume_decreased = self._volume_decreased(technical.weekly_volume)

            strategy_type = None
            if abs(disparity_20ma) <= self.pullback_band:
                strategy_type = "WEEKLY_20MA_PULLBACK"
            elif abs(disparity_60ma) <= self.pullback_band:
                strategy_type = "WEEKLY_60MA_PULLBACK"

            checks = {
                "monthly_trend_passed": monthly_trend_passed,
                "listed_period_passed": listed_period_passed,
                "weekly_disparity_20ma": disparity_20ma,
                "weekly_disparity_60ma": disparity_60ma,
                "volume_decreased": volume_decreased,
                "strategy_type": strategy_type,
            }
            is_passed = monthly_trend_passed and listed_period_passed and volume_decreased and strategy_type is not None
            explain_items.append(
                {
                    "ticker": fundamental.ticker,
                    "name": fundamental.name,
                    "technical_pullback": {"passed": is_passed, **checks},
                }
            )
            if is_passed:
                passed.append({"fundamental": fundamental, "technical": technical, **checks})

        return passed, explain_items

    def _monthly_uptrend(self, monthly_close: list[float]) -> bool:
        ma5 = self._moving_average(monthly_close, 5)
        ma20 = self._moving_average(monthly_close, 20)
        return ma5 > ma20 and monthly_close[-1] > ma5

    def _volume_decreased(self, weekly_volume: list[float]) -> bool:
        if len(weekly_volume) < 5:
            return False
        previous_average = sum(weekly_volume[-5:-1]) / 4
        return weekly_volume[-1] < previous_average

    @staticmethod
    def _moving_average(values: list[float], window: int) -> float:
        if len(values) < window:
            return 0.0
        return sum(values[-window:]) / window

    @staticmethod
    def _disparity(value: float, moving_average: float) -> float:
        if moving_average == 0:
            return 999.0
        return value / moving_average - 1

    @staticmethod
    def _explain_missing(fundamental: FundamentalRecord) -> dict[str, Any]:
        return {
            "ticker": fundamental.ticker,
            "name": fundamental.name,
            "technical_pullback": {"passed": False, "reason": "missing_technical_data"},
        }
