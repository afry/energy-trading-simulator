from abc import ABC, abstractmethod
from typing import List

from ..bid import Bid
from ..data_store import DataStore
from ..trade import Trade, Market


class IAgent(ABC):
    """Interface for agents to implement"""

    def __init__(self, guid: str, data_store: DataStore):
        self.guid = guid
        self.data_store = data_store

    @abstractmethod
    def make_bids(self, period, clearing_prices_dict: dict):
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
    def make_trade_given_clearing_price(self, period, clearing_price: float, clearing_prices_dict: dict,
                                        accepted_bids_for_agent: List[Bid]):
        # Once market solver has decided a clearing price, it will send it to the agents with this method
        # Should return a Trade
        pass

    def construct_bid(self, action, resource, quantity, price):
        return Bid(action, resource, quantity, price, self.guid, False)

    def construct_trade(self, action, resource, quantity, price, market, period):
        return Trade(action, resource, quantity, price, self.guid, False, market, period)

    def get_external_grid_buy_price(self, period):
        wholesale_price = self.data_store.get_wholesale_price(period)

        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325, Varberg Energi can pay an extra
        # remuneration on top of the Nordpool spot price. This can vary, "depending on for example membership".
        # Might make sense to make this number configurable.
        remuneration_modifier = 0

        return wholesale_price + remuneration_modifier


def get_price_and_market_to_use_when_buying(clearing_price: float, retail_price: float):
    if clearing_price <= retail_price:
        return clearing_price, Market.LOCAL
    else:
        return retail_price, Market.EXTERNAL


def get_price_and_market_to_use_when_selling(clearing_price: float, wholesale_price: float):
    if clearing_price >= wholesale_price:
        return clearing_price, Market.LOCAL
    else:
        return wholesale_price, Market.EXTERNAL
