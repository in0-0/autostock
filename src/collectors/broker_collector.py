from __future__ import annotations

import importlib
from datetime import datetime
from typing import Iterable

from src.brokers.base import BrokerConnector
from src.models import BrokerCollectionResult, PortfolioState


def load_broker_connector(dotted_path: str) -> BrokerConnector:
    module_name, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    connector_class = getattr(module, class_name)
    return connector_class()


def collect_broker_snapshots(connector_paths: Iterable[str]) -> BrokerCollectionResult:
    result = BrokerCollectionResult()
    for connector_path in connector_paths:
        try:
            connector = load_broker_connector(connector_path)
            result.snapshots.append(connector.fetch_snapshot())
        except Exception:
            result.failed_brokers.append(connector_path)
    return result


def merge_portfolio(
    collection: BrokerCollectionResult,
    *,
    ip_changed_flag: bool = False,
    now: datetime | None = None,
) -> PortfolioState:
    from src.collectors.portfolio_source import broker_collection_to_source_result, merge_portfolio_sources

    portfolio = merge_portfolio_sources(
        broker_collection_to_source_result(collection),
        ip_changed_flag=ip_changed_flag,
        now=now,
    )
    return portfolio.model_copy(
        update={
            "failed_brokers": collection.failed_brokers,
            "failed_sources": [],
        }
    )
