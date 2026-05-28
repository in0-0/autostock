from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import BrokerSnapshot


class BrokerConnector(ABC):
    broker_name: str

    @abstractmethod
    def fetch_snapshot(self) -> BrokerSnapshot:
        raise NotImplementedError
