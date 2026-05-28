from __future__ import annotations

from src.models import MacroStatus


def _above_moving_average(values: list[float], window: int) -> bool:
    if len(values) < window:
        return False
    moving_average = sum(values[-window:]) / window
    return values[-1] > moving_average


class MacroEngine:
    def evaluate(self, macro_data: dict) -> tuple[MacroStatus, dict]:
        kospi_above = _above_moving_average(macro_data["kospi_monthly_close"], 10)
        kosdaq_above = _above_moving_average(macro_data["kosdaq_monthly_close"], 10)

        if kospi_above and kosdaq_above:
            status = MacroStatus.NORMAL
        elif kospi_above and not kosdaq_above:
            status = MacroStatus.CAUTION
        else:
            status = MacroStatus.RISK_OFF

        indicators = {
            "kospi_above_10ma": kospi_above,
            "kosdaq_above_10ma": kosdaq_above,
            "us_rate": macro_data.get("us_rate"),
            "yield_curve_10y2y": macro_data.get("yield_curve_10y2y"),
        }
        return status, indicators
