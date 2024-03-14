import datetime
import logging
from typing import Union

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.trade import Resource
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice

logger = logging.getLogger(__name__)


class GridAgent(IAgent):
    resource: Resource
    max_transfer_per_hour: float
    pricing: Union[HeatingPrice, ElectricityPrice]
    can_buy: bool

    def __init__(self, local_market_enabled: bool, pricing: Union[HeatingPrice, ElectricityPrice], resource: Resource,
                 can_buy: bool, max_transfer_per_hour: float, guid: str = "GridAgent"):
        super().__init__(guid, local_market_enabled)
        self.resource = resource
        self.pricing = self._is_valid_pricing(pricing)
        self.max_transfer_per_hour = max_transfer_per_hour
        self.can_buy = can_buy
        self.resource_loss_per_side = self.pricing.heat_transfer_loss_per_side if isinstance(self.pricing,
                                                                                             HeatingPrice) else 0.0
        
    def _is_valid_pricing(self, pricing: Union[HeatingPrice, ElectricityPrice]):
        if self.resource != pricing.resource:
            raise ValueError("Resource and pricing resource for GridAgent does not match up!")
        return pricing

    def get_actual_usage_for_resource(self, period: datetime.datetime, resource: Resource) -> float:
        pass
