from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any


class MacroStatus(str, Enum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    RISK_OFF = "RISK_OFF"


class ExitSignal(str, Enum):
    NONE = "NONE"
    WARNING = "WARNING"
    REDUCE = "REDUCE"
    EXIT = "EXIT"


class RecommendationAction(str, Enum):
    BUY = "BUY"
    HOLD_STRONG = "HOLD_STRONG"
    HOLD_WARNING = "HOLD_WARNING"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    SKIP = "SKIP"


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


class Serializable:
    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        del mode
        return _serialize(asdict(self))

    def model_copy(self, update: dict[str, Any] | None = None) -> Any:
        return replace(self, **(update or {}))


@dataclass
class BrokerPosition(Serializable):
    ticker: str
    stock_name: str
    quantity: int
    average_price: int
    current_price: int


@dataclass
class BrokerSnapshot(Serializable):
    broker_name: str
    account_id: str
    krw_deposit: int
    positions: list[BrokerPosition] = field(default_factory=list)


@dataclass
class BrokerCollectionResult(Serializable):
    snapshots: list[BrokerSnapshot] = field(default_factory=list)
    failed_brokers: list[str] = field(default_factory=list)

    @property
    def partial_success(self) -> bool:
        return bool(self.failed_brokers)


@dataclass
class PortfolioPosition(Serializable):
    stock_name: str
    quantity: int
    weighted_average_price: int
    current_price: int
    market_value: int
    current_ratio: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioState(Serializable):
    updated_at: datetime
    total_krw_evaluation: int
    total_krw_deposit: int
    ip_changed_flag: bool = False
    partial_success: bool = False
    failed_brokers: list[str] = field(default_factory=list)
    failed_sources: list[str] = field(default_factory=list)
    source_warnings: list[str] = field(default_factory=list)
    positions: dict[str, PortfolioPosition] = field(default_factory=dict)


@dataclass
class FundamentalRecord(Serializable):
    ticker: str
    name: str
    roe_3y_avg: float
    debt_ratio: float
    operating_margin: float
    net_income_growth: float
    operating_income_growth: float
    previous_net_income: int
    current_net_income: int
    peg: float
    industry: str = "DEFAULT"


@dataclass
class TechnicalRecord(Serializable):
    ticker: str
    monthly_close: list[float]
    weekly_close: list[float]
    weekly_volume: list[float]
    listed_weeks: int


@dataclass
class Candidate(Serializable):
    ticker: str
    name: str
    peg: float
    strategy_type: str
    current_price: int
    filters: dict[str, Any] = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    provider: str | None = None
    exit_signal: ExitSignal = ExitSignal.NONE
    final_rank: int | None = None


@dataclass
class TradeGuide(Serializable):
    ticker: str
    name: str
    action: RecommendationAction
    reason: str
    target_ratio: float
    current_ratio: float
    quantity_delta: int = 0
    required_cash: int = 0


@dataclass
class ExplainLog(Serializable):
    generated_at: datetime
    macro_status: MacroStatus
    macro_indicators: dict[str, Any]
    partial_success: bool
    failed_brokers: list[str]
    items: list[dict[str, Any]]
    failed_sources: list[str] = field(default_factory=list)
    source_warnings: list[str] = field(default_factory=list)
    portfolio_source_type: str | None = None
    market_data_provider: str | None = None
    macro_provider: str | None = None
    market_data_warnings: list[str] = field(default_factory=list)
