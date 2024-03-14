import datetime
from abc import ABC, abstractmethod
from typing import Dict

from tradingplatformpoc.market.bid import Resource


class IAgent(ABC):
    """Interface for agents to implement"""

    guid: str
    local_market_enabled: bool

    def __init__(self, guid: str, local_market_enabled: bool):
        self.guid = guid
        self.local_market_enabled = local_market_enabled

    @abstractmethod
    def get_actual_usage_for_resource(self, period: datetime.datetime, resource: Resource) -> float:
        # Return actual usage/supply for the trading horizon, and the specified resource
        # If negative, it means the agent was a net-producer for the trading period
        pass

    def get_actual_usage(self, period: datetime.datetime) -> Dict[Resource, float]:
        # If negative, it means the agent was a net-producer for the trading period
        return {res: self.get_actual_usage_for_resource(period, res) for res in Resource}
