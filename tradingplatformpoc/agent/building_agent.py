import math

from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_buying
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.data_store import DataStore


class BuildingAgent(IAgent):

    def __init__(self, data_store: DataStore, guid="BuildingAgent"):
        super().__init__(guid)
        self.data_store = data_store

    def make_bids(self, period):
        # The building should make a bid for purchasing energy
        bids = [self.construct_bid(Action.BUY, Resource.ELECTRICITY, self.make_prognosis(period), math.inf)]
        # This demand must be fulfilled - therefore price is inf
        return bids

    def make_prognosis(self, period):
        # The building should make a prognosis for how much energy will be required
        electricity_demand = self.data_store.get_tornet_household_electricity_consumed(period)
        # FUTURE: Make a prognosis, instead of using the actual
        return electricity_demand

    def get_actual_usage(self, period):
        actual_usage = self.data_store.get_tornet_household_electricity_consumed(period)
        return actual_usage

    def make_trade_given_clearing_price(self, period, clearing_price):
        retail_price = self.data_store.get_retail_price(period)
        price_to_use, market_to_use = get_price_and_market_to_use_when_buying(clearing_price, retail_price)
        return self.construct_trade(Action.BUY, Resource.ELECTRICITY, self.get_actual_usage(period), price_to_use,
                                    market_to_use, period)