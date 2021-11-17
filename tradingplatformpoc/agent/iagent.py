from abc import ABC, abstractmethod

from ..bid import Bid
from ..trade import Trade, Market


class IAgent(ABC):
    """Interface for agents to implement"""

    def __init__(self, guid: str):
        self.guid = guid

    @abstractmethod
    def make_bids(self, period):
        # Make a bid for produced or needed energy for next time step
        pass

    @abstractmethod
    def make_prognosis(self, period):
        # Make resource prognosis for the trading horizon
        pass

    @abstractmethod
    def get_actual_usage(self, period):
        # Return actual resource usage/supply for the trading horizon
        # If negative, it means the agent was a net-producer for the trading period
        pass

    @abstractmethod
    def make_trade_given_clearing_price(self, period, clearing_price):
        # Once market solver has decided a clearing price, it will send it to the agents with this method
        # Should return a Trade
        pass

    def construct_bid(self, action, resource, quantity, price):
        return Bid(action, resource, quantity, price, self.guid)

    def construct_trade(self, action, resource, quantity, price, market, period):
        return Trade(action, resource, quantity, price, self.guid, market, period)


def get_price_and_market_to_use_when_buying(clearing_price, retail_price):
    if clearing_price <= retail_price:
        return clearing_price, Market.LOCAL
    else:
        return retail_price, Market.EXTERNAL


def get_price_and_market_to_use_when_selling(clearing_price, wholesale_price):
    if clearing_price >= wholesale_price:
        return clearing_price, Market.LOCAL
    else:
        return wholesale_price, Market.EXTERNAL
