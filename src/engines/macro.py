from __future__ import annotations

from src.models import MacroStatus


def _above_moving_average(values: list[float], window: int) -> bool:
    if len(values) < window:
        return False
    moving_average = sum(values[-window:]) / window
    return values[-1] > moving_average


class MacroEngine:
    def evaluate(self, macro_data: dict) -> tuple[MacroStatus, dict]:
        kospi_values = macro_data.get("kospi_monthly_close") or []
        kosdaq_values = macro_data.get("kosdaq_monthly_close") or []
        macro_data_available = len(kospi_values) >= 10 and len(kosdaq_values) >= 10
        kospi_above = _above_moving_average(kospi_values, 10)
        kosdaq_above = _above_moving_average(kosdaq_values, 10)

        if not macro_data_available:
            status = MacroStatus.CAUTION
        elif kospi_above and kosdaq_above:
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
            "macro_data_available": macro_data_available,
            "macro_data_unavailable": not macro_data_available,
        }
        return status, indicators
