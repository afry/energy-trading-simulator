import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from tradingplatformpoc import trading_platform_utils
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.digitaltwin.battery import Battery
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice

logger = logging.getLogger(__name__)


class BlockAgent(IAgent):

    heat_pricing: HeatingPrice
    electricity_pricing: ElectricityPrice
    digital_twin: StaticDigitalTwin
    battery: Battery
    can_sell_heat_to_external: bool
    heat_pump_max_input: float
    heat_pump_max_output: float
    booster_pump_max_input: float
    booster_pump_max_output: float
    acc_tank_volume: float

    def __init__(self, local_market_enabled: bool, heat_pricing: HeatingPrice, electricity_pricing: ElectricityPrice,
                 digital_twin: StaticDigitalTwin, can_sell_heat_to_external: bool, heat_pump_max_input: float = 0,
                 heat_pump_max_output: float = 0, booster_pump_max_input: float = 0, booster_pump_max_output: float = 0,
                 acc_tank_volume: float = 0,
                 battery: Optional[Battery] = None, guid="BlockAgent"):
        super().__init__(guid, local_market_enabled)
        self.heat_pricing = heat_pricing
        self.electricity_pricing = electricity_pricing
        self.digital_twin = digital_twin
        self.heat_pump_max_input = heat_pump_max_input
        self.heat_pump_max_output = heat_pump_max_output
        self.booster_pump_max_input = booster_pump_max_input
        self.booster_pump_max_output = booster_pump_max_output
        self.acc_tank_volume = acc_tank_volume
        self.can_sell_heat_to_external = can_sell_heat_to_external
        self.battery = Battery(0, 0, 0, 0) if battery is None else battery

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None) -> List[GrossBid]:
        pass

    def make_prognosis_for_resource(self, period: datetime.datetime, resource: Resource) -> float:
        # The agent should make a prognosis for how much energy will be required
        prev_trading_period = trading_platform_utils.minus_n_hours(period, 1)
        try:
            electricity_demand_prev = self.digital_twin.get_consumption(prev_trading_period, resource)
            electricity_prod_prev = self.digital_twin.get_production(prev_trading_period, resource)
        except KeyError:
            # First time step, haven't got a previous value to use. Will go with a perfect prediction here
            electricity_demand_prev = self.digital_twin.get_consumption(period, resource)
            electricity_prod_prev = self.digital_twin.get_production(period, resource)
        return electricity_demand_prev - electricity_prod_prev

    def get_actual_usage_for_resource(self, period: datetime.datetime, resource: Resource) -> float:
        actual_consumption = self.digital_twin.get_consumption(period, resource)
        actual_production = self.digital_twin.get_production(period, resource)
        return actual_consumption - actual_production

    def make_trades_given_clearing_price(self, period: datetime.datetime, clearing_prices: Dict[Resource, float],
                                         accepted_bids_for_agent: List[NetBidWithAcceptanceStatus]) -> \
            Tuple[List[Trade], Dict[TradeMetadataKey, Any]]:
        pass
