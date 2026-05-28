from __future__ import annotations

from typing import Any

from src.models import FundamentalRecord


class FundamentalEngine:
    def __init__(self, filter_settings: dict[str, Any]) -> None:
        self.filter_settings = filter_settings

    def evaluate(self, records: list[FundamentalRecord]) -> tuple[list[FundamentalRecord], list[dict[str, Any]]]:
        passed: list[FundamentalRecord] = []
        explain_items: list[dict[str, Any]] = []

        for record in records:
            min_margin = self._min_operating_margin(record.industry)
            is_turnaround = record.previous_net_income < 0 < record.current_net_income
            growth_divergence = abs(record.net_income_growth - record.operating_income_growth)
            checks = {
                "roe_3y_avg": record.roe_3y_avg,
                "roe_passed": record.roe_3y_avg >= self.filter_settings["roe_3y_avg_min"],
                "debt_ratio": record.debt_ratio,
                "debt_passed": record.debt_ratio <= self.filter_settings["debt_ratio_max"],
                "operating_margin": record.operating_margin,
                "operating_margin_min": min_margin,
                "operating_margin_passed": record.operating_margin >= min_margin,
                "is_turnaround": is_turnaround,
                "growth_divergence": growth_divergence,
                "growth_divergence_passed": growth_divergence < self.filter_settings["max_growth_divergence"],
            }
            is_passed = all(
                [
                    checks["roe_passed"],
                    checks["debt_passed"],
                    checks["operating_margin_passed"],
                    not is_turnaround,
                    checks["growth_divergence_passed"],
                ]
            )
            explain_items.append(
                {
                    "ticker": record.ticker,
                    "name": record.name,
                    "financial_cutoff": {"passed": is_passed, **checks},
                    "peg": record.peg,
                }
            )
            if is_passed:
                passed.append(record)

        return passed, explain_items

    def _min_operating_margin(self, industry: str) -> float:
        mapping = self.filter_settings["min_operating_margin"]
        return float(mapping.get(industry, mapping["DEFAULT"]))
