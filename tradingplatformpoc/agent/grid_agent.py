import datetime
import logging

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.trade import Resource

logger = logging.getLogger(__name__)


class GridAgent(IAgent):
    resource: Resource
    max_transfer_per_hour: float
    can_buy: bool

    def __init__(self, resource: Resource, can_buy: bool, max_transfer_per_hour: float, guid: str = "GridAgent"):
        super().__init__(guid)
        self.resource = resource
        self.max_transfer_per_hour = max_transfer_per_hour
        self.can_buy = can_buy

    def get_actual_usage_for_resource(self, period: datetime.datetime, resource: Resource) -> float:
        pass
