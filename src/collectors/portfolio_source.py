from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from src.brokers.base import BrokerConnector
from src.collectors.broker_collector import collect_broker_snapshots
from src.models import BrokerCollectionResult, PortfolioPosition, PortfolioState


@dataclass
class PortfolioSourcePosition:
    ticker: str
    stock_name: str
    quantity: int
    average_price: int
    current_price: int
    market_value: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class PortfolioSourceSnapshot:
    source_name: str
    source_type: str
    cash: int = 0
    account_label: str | None = None
    positions: list[PortfolioSourcePosition] = field(default_factory=list)


@dataclass
class PortfolioSourceResult:
    snapshots: list[PortfolioSourceSnapshot] = field(default_factory=list)
    failed_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_type: str = "unknown"
    telemetry: dict[str, object] = field(default_factory=dict)

    @property
    def partial_success(self) -> bool:
        return bool(self.failed_sources)


class PortfolioSource(Protocol):
    source_name: str
    source_type: str

    def fetch(self) -> PortfolioSourceResult:
        raise NotImplementedError


def broker_collection_to_source_result(collection: BrokerCollectionResult) -> PortfolioSourceResult:
    snapshots: list[PortfolioSourceSnapshot] = []
    for snapshot in collection.snapshots:
        snapshots.append(
            PortfolioSourceSnapshot(
                source_name=snapshot.broker_name,
                source_type="broker",
                cash=snapshot.krw_deposit,
                account_label=None,
                positions=[
                    PortfolioSourcePosition(
                        ticker=position.ticker,
                        stock_name=position.stock_name,
                        quantity=position.quantity,
                        average_price=position.average_price,
                        current_price=position.current_price,
                    )
                    for position in snapshot.positions
                ],
            )
        )
    return PortfolioSourceResult(
        snapshots=snapshots,
        failed_sources=list(collection.failed_brokers),
        source_type="broker",
    )


class BrokerPortfolioSource:
    source_name = "broker_connectors"
    source_type = "broker"

    def __init__(self, connector_paths: list[str]) -> None:
        self.connector_paths = connector_paths

    def fetch(self) -> PortfolioSourceResult:
        return broker_collection_to_source_result(collect_broker_snapshots(self.connector_paths))


class BrokerConnectorPortfolioSource:
    source_type = "broker"

    def __init__(self, connector: BrokerConnector) -> None:
        self.connector = connector
        self.source_name = connector.broker_name

    def fetch(self) -> PortfolioSourceResult:
        snapshot = self.connector.fetch_snapshot()
        return broker_collection_to_source_result(BrokerCollectionResult(snapshots=[snapshot]))


def merge_portfolio_sources(
    result: PortfolioSourceResult,
    *,
    ip_changed_flag: bool = False,
    now: datetime | None = None,
) -> PortfolioState:
    grouped: dict[str, list[PortfolioSourcePosition]] = defaultdict(list)
    total_deposit = 0

    for snapshot in result.snapshots:
        total_deposit += snapshot.cash
        for position in snapshot.positions:
            grouped[position.ticker].append(position)

    merged_positions: dict[str, PortfolioPosition] = {}
    total_market_value = 0

    for ticker, positions in grouped.items():
        quantity = sum(position.quantity for position in positions)
        if quantity <= 0:
            continue
        weighted_average_price = int(
            sum(position.quantity * position.average_price for position in positions) / quantity + 0.5
        )
        current_price = int(
            sum(position.quantity * position.current_price for position in positions) / quantity + 0.5
        )
        market_value = sum(
            position.market_value if position.market_value is not None else position.quantity * position.current_price
            for position in positions
        )
        metadata: dict[str, object] = {}
        for position in positions:
            for key, value in position.metadata.items():
                if value not in {"", None}:
                    metadata.setdefault(key, value)
        total_market_value += market_value
        merged_positions[ticker] = PortfolioPosition(
            stock_name=positions[0].stock_name,
            quantity=quantity,
            weighted_average_price=weighted_average_price,
            current_price=current_price,
            market_value=market_value,
            current_ratio=0.0,
            metadata=metadata,
        )

    total_evaluation = total_deposit + total_market_value
    if total_evaluation > 0:
        for ticker, position in merged_positions.items():
            merged_positions[ticker] = position.model_copy(
                update={"current_ratio": position.market_value / total_evaluation}
            )

    return PortfolioState(
        updated_at=now or datetime.now(),
        ip_changed_flag=ip_changed_flag,
        partial_success=result.partial_success,
        failed_brokers=[],
        failed_sources=result.failed_sources,
        source_warnings=result.warnings,
        total_krw_evaluation=total_evaluation,
        total_krw_deposit=total_deposit,
        positions=merged_positions,
    )
