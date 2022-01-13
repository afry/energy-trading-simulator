import math
from typing import List

from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_buying, \
    get_price_and_market_to_use_when_selling
from tradingplatformpoc.bid import Action, Resource, Bid
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.trading_platform_utils import minus_n_hours


class BuildingAgent(IAgent):

    def __init__(self, data_store: DataStore, digital_twin: StaticDigitalTwin, guid="BuildingAgent"):
        super().__init__(guid, data_store)
        self.digital_twin = digital_twin

    def make_bids(self, period, clearing_prices_dict: dict = None):
        # The building should make a bid for purchasing energy, or selling if it has a surplus
        electricity_needed = self.make_prognosis(period)
        bids = []
        if electricity_needed > 0:
            bids.append(self.construct_bid(Action.BUY, Resource.ELECTRICITY, electricity_needed, math.inf))
            # This demand must be fulfilled - therefore price is inf
        elif electricity_needed < 0:
            bids.append(self.construct_bid(Action.SELL, Resource.ELECTRICITY, -electricity_needed,
                                           self.get_external_grid_buy_price(period)))
            # If the building doesn't have it's own battery, then surplus electricity must be sold, so price is 0
        return bids

    def make_prognosis(self, period):
        # The building should make a prognosis for how much energy will be required
        prev_trading_period = minus_n_hours(period, 1)
        try:
            electricity_demand_prev = self.digital_twin.get_consumption(prev_trading_period, Resource.ELECTRICITY)
            electricity_prod_prev = self.digital_twin.get_production(prev_trading_period, Resource.ELECTRICITY)
        except KeyError:
            # First time step, haven't got a previous value to use. Will go with a perfect prediction here
            electricity_demand_prev = self.digital_twin.get_consumption(period, Resource.ELECTRICITY)
            electricity_prod_prev = self.digital_twin.get_production(period, Resource.ELECTRICITY)
        return electricity_demand_prev - electricity_prod_prev

    def get_actual_usage(self, period):
        actual_consumption = self.digital_twin.get_consumption(period, Resource.ELECTRICITY)
        actual_production = self.digital_twin.get_production(period, Resource.ELECTRICITY)
        return actual_consumption - actual_production

    def make_trade_given_clearing_price(self, period, clearing_price: float, clearing_prices_dict: dict,
                                        accepted_bids_for_agent: List[Bid]):
        retail_price = self.data_store.get_retail_price(period)
        wholesale_price = self.data_store.get_wholesale_price(period)
        usage = self.get_actual_usage(period)
        if usage >= 0:
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(clearing_price, retail_price)
            return self.construct_trade(Action.BUY, Resource.ELECTRICITY, usage, price_to_use, market_to_use, period)
        else:
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(clearing_price, wholesale_price)
            return self.construct_trade(Action.SELL, Resource.ELECTRICITY, -usage, price_to_use, market_to_use, period)
