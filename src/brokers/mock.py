from __future__ import annotations

from src.brokers.base import BrokerConnector
from src.models import BrokerPosition, BrokerSnapshot


class MockBrokerConnector(BrokerConnector):
    broker_name = "MOCK"

    def fetch_snapshot(self) -> BrokerSnapshot:
        return BrokerSnapshot(
            broker_name=self.broker_name,
            account_id="mock-001",
            krw_deposit=12_000_000,
            positions=[
                BrokerPosition(
                    ticker="005930",
                    stock_name="삼성전자",
                    quantity=150,
                    average_price=72_300,
                    current_price=75_000,
                ),
                BrokerPosition(
                    ticker="000660",
                    stock_name="SK하이닉스",
                    quantity=30,
                    average_price=180_000,
                    current_price=190_000,
                ),
            ],
        )
