import datetime
from abc import ABC, abstractmethod
from typing import Dict, List, Union

import numpy as np

from ..bid import Action, Bid, BidWithAcceptanceStatus, Resource
from ..data_store import DataStore
from ..trade import Market, Trade


class IAgent(ABC):
    """Interface for agents to implement"""

    def __init__(self, guid: str, data_store: DataStore):
        self.guid = guid
        self.data_store = data_store

    @abstractmethod
    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None]):
        # Make a bid for produced or needed energy for next time step
        pass

    @abstractmethod
    def make_prognosis(self, period: datetime.datetime, resource: Resource):
        # Make resource prognosis for the trading horizon, and the specified resource
        pass

    @abstractmethod
    def get_actual_usage(self, period: datetime.datetime, resource: Resource):
        # Return actual usage/supply for the trading horizon, and the specified resource
        # If negative, it means the agent was a net-producer for the trading period
        pass

    @abstractmethod
    def make_trades_given_clearing_price(self, period: datetime.datetime, clearing_prices: Dict[Resource, float],
                                         accepted_bids_for_agent: List[BidWithAcceptanceStatus]) -> List[Trade]:
        """
        Once market solver has decided a clearing price for each resource, it will send them to the agents with this
        method.
        @return: Some trades - but not more than 1 per resource
        """
        pass

    def construct_bid(self, action: Action, resource: Resource, quantity: float, price: float) -> Bid:
        return Bid(action, resource, quantity, price, self.guid, False)

    def construct_trade(self, action: Action, resource: Resource, quantity: float, price: float, market: Market,
                        period: datetime.datetime) -> Trade:
        return Trade(action, resource, quantity, price, self.guid, False, market, period)

    def get_external_grid_buy_price(self, period: datetime.datetime, resource: Resource):
        wholesale_price = self.data_store.get_estimated_wholesale_price(period, resource)

        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325, Varberg Energi can pay an extra
        # remuneration on top of the Nordpool spot price. This can vary, "depending on for example membership".
        # Might make sense to make this number configurable.
        remuneration_modifier = 0

        return wholesale_price + remuneration_modifier


def get_price_and_market_to_use_when_buying(clearing_price: float, retail_price: float):
    if clearing_price != np.nan and clearing_price <= retail_price:
        return clearing_price, Market.LOCAL
    else:
        return retail_price, Market.EXTERNAL


def get_price_and_market_to_use_when_selling(clearing_price: float, wholesale_price: float):
    if clearing_price != np.nan and clearing_price >= wholesale_price:
        return clearing_price, Market.LOCAL
    else:
        return wholesale_price, Market.EXTERNAL
