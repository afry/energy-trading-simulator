import datetime
import math
from typing import Dict, List, Union

from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_buying, \
    get_price_and_market_to_use_when_selling
from tradingplatformpoc.bid import Action, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.heat_pump import HeatPump
from tradingplatformpoc.trade import Trade
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES, minus_n_hours


class BuildingAgent(IAgent):

    def __init__(self, data_store: DataStore, heat_pumps: List[HeatPump], digital_twin: StaticDigitalTwin,
                 guid="BuildingAgent"):
        super().__init__(guid, data_store)
        self.digital_twin = digital_twin
        self.heat_pumps = heat_pumps

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None):
        # The building should make a bid for purchasing energy, or selling if it has a surplus
        bids = []

        if self.heat_pump is None:
            # In this case, we can treat is as we always have previously, just make independent bids for the
            # electricity and heating energy the agent needs.
            for resource in ALL_IMPLEMENTED_RESOURCES:
                resource_needed = self.make_prognosis(period, resource)
                if resource_needed > 0:
                    bids.append(self.construct_bid(Action.BUY, resource, resource_needed, math.inf))
                    # This demand must be fulfilled - therefore price is inf
                elif resource_needed < 0:
                    bids.append(self.construct_bid(Action.SELL, resource, -resource_needed,
                                                self.get_external_grid_buy_price(period, resource)))
                    # If the building doesn't have it's own battery, then surplus energy _must_ be sold, so price is 0
            return bids
        else:
            # TODO: Here we need to figure out the new bidding logic
            # We can either buy heat for heating
            for resource in ALL_IMPLEMENTED_RESOURCES:
                resource_needed = self.make_prognosis(period, resource)

    def make_prognosis(self, period: datetime.datetime, resource: Resource):
        # The building should make a prognosis for how much energy will be required
        prev_trading_period = minus_n_hours(period, 1)
        try:
            electricity_demand_prev = self.digital_twin.get_consumption(prev_trading_period, resource)
            electricity_prod_prev = self.digital_twin.get_production(prev_trading_period, resource)
        except KeyError:
            # First time step, haven't got a previous value to use. Will go with a perfect prediction here
            electricity_demand_prev = self.digital_twin.get_consumption(period, resource)
            electricity_prod_prev = self.digital_twin.get_production(period, resource)
        return electricity_demand_prev - electricity_prod_prev

    def get_actual_usage(self, period: datetime.datetime, resource: Resource):
        actual_consumption = self.digital_twin.get_consumption(period, resource)
        actual_production = self.digital_twin.get_production(period, resource)
        return actual_consumption - actual_production

    def make_trades_given_clearing_price(self, period: datetime.datetime, clearing_prices: Dict[Resource, float],
                                         accepted_bids_for_agent: List[BidWithAcceptanceStatus]) -> List[Trade]:
        trades = []
        for resource in ALL_IMPLEMENTED_RESOURCES:
            retail_price = self.data_store.get_estimated_retail_price(period, resource)
            wholesale_price = self.data_store.get_estimated_wholesale_price(period, resource)
            usage = self.get_actual_usage(period, resource)
            clearing_price = clearing_prices[resource]
            if usage > 0:
                price_to_use, market_to_use = get_price_and_market_to_use_when_buying(clearing_price, retail_price)
                trades.append(self.construct_trade(Action.BUY, resource, usage, price_to_use, market_to_use, period))
            elif usage < 0:
                price_to_use, market_to_use = get_price_and_market_to_use_when_selling(clearing_price, wholesale_price)
                trades.append(self.construct_trade(Action.SELL, resource, -usage, price_to_use, market_to_use, period))
        return trades
