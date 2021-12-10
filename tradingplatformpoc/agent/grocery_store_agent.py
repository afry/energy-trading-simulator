import math

from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_buying, \
    get_price_and_market_to_use_when_selling
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.trading_platform_utils import minus_n_hours


class GroceryStoreAgent(IAgent):
    """Currently very similar to BuildingAgent. May in the future sell excess heat."""

    def __init__(self, data_store: DataStore, guid="GroceryStoreAgent"):
        super().__init__(guid)
        self.data_store = data_store

    def make_bids(self, period):
        # The building should make a bid for purchasing energy
        electricity_needed = self.make_prognosis(period)
        bids = []
        if electricity_needed > 0:
            bids.append(self.construct_bid(Action.BUY, Resource.ELECTRICITY, electricity_needed, math.inf))
            # This demand must be fulfilled - therefore price is inf
        elif electricity_needed < 0:
            bids.append(self.construct_bid(Action.SELL, Resource.ELECTRICITY, -electricity_needed, 0))
            # If the store doesn't have it's own battery, then surplus electricity must be sold, so price is 0
        return bids

    def make_prognosis(self, period):
        # The building should make a prognosis for how much energy will be required.
        # If negative, it means there is a surplus
        prev_trading_period = minus_n_hours(period, 1)
        try:
            electricity_demand = self.data_store.get_coop_electricity_consumed(prev_trading_period)
            electricity_supply = self.data_store.get_coop_pv_produced(prev_trading_period)
        except KeyError:
            # First time step, haven't got a previous value to use. Will go with a perfect prediction here
            electricity_demand = self.data_store.get_coop_electricity_consumed(period)
            electricity_supply = self.data_store.get_coop_pv_produced(period)
        return electricity_demand - electricity_supply

    def get_actual_usage(self, period):
        electricity_demand = self.data_store.get_coop_electricity_consumed(period)
        electricity_supply = self.data_store.get_coop_pv_produced(period)
        return electricity_demand - electricity_supply

    def make_trade_given_clearing_price(self, period, clearing_price):
        retail_price = self.data_store.get_retail_price(period)
        wholesale_price = self.data_store.get_wholesale_price(period)
        usage = self.get_actual_usage(period)
        if usage >= 0:
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(clearing_price, retail_price)
            return self.construct_trade(Action.BUY, Resource.ELECTRICITY, usage, price_to_use, market_to_use, period)
        else:
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(clearing_price, wholesale_price)
            return self.construct_trade(Action.SELL, Resource.ELECTRICITY, usage, price_to_use, market_to_use, period)