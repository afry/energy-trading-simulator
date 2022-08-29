import datetime
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Union

import numpy as np

from ..bid import Action, Bid, BidWithAcceptanceStatus, Resource
from ..data_store import DataStore
from ..trade import Market, Trade, TradeMetadataKey


class IAgent(ABC):
    """Interface for agents to implement"""

    guid: str
    data_store: DataStore

    def __init__(self, guid: str, data_store: DataStore):
        self.guid = guid
        self.data_store = data_store

    @abstractmethod
    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None]) -> List[Bid]:
        # Make a bid for produced or needed energy for next time step
        pass

    @abstractmethod
    def make_prognosis(self, period: datetime.datetime, resource: Resource) -> float:
        # Make resource prognosis for the trading horizon, and the specified resource
        pass

    @abstractmethod
    def get_actual_usage(self, period: datetime.datetime, resource: Resource) -> float:
        # Return actual usage/supply for the trading horizon, and the specified resource
        # If negative, it means the agent was a net-producer for the trading period
        pass

    @abstractmethod
    def make_trades_given_clearing_price(self, period: datetime.datetime, clearing_prices: Dict[Resource, float],
                                         accepted_bids_for_agent: List[BidWithAcceptanceStatus]) -> \
            Tuple[List[Trade], Dict[TradeMetadataKey, Any]]:
        """
        Once market solver has decided a clearing price for each resource, it will send them to the agents with this
        method.
        @return: A tuple: 1. Some trades - but not more than 1 per resource. 2. Metadata
        """
        pass

    def construct_elec_bid(self, action: Action, quantity: float, price: float) -> Bid:
        return Bid(action, Resource.ELECTRICITY, quantity, price, self.guid, False)

    def construct_sell_heat_bid(self, quantity: float, price: float) -> Bid:
        # Heat transfer loss added
        quantity_after_loss = quantity * (1 - self.data_store.heat_transfer_loss_per_side)
        return Bid(Action.SELL, Resource.HEATING, quantity_after_loss, price, self.guid, False)

    def construct_buy_heat_bid(self, quantity_needed: float, price: float) -> Bid:
        # The heat transfer loss needs to be accounted for
        quantity_to_buy = quantity_needed / (1 - self.data_store.heat_transfer_loss_per_side)
        return Bid(Action.BUY, Resource.HEATING, quantity_to_buy, price, self.guid, False)

    def construct_elec_trade(self, action: Action, quantity: float, price: float, market: Market,
                             period: datetime.datetime) -> Trade:
        return Trade(action, Resource.ELECTRICITY, quantity, price, self.guid, False, market, period)

    def construct_sell_heat_trade(self, quantity: float, price: float, market: Market, period: datetime.datetime) -> \
            Trade:
        # Heat transfer loss added
        quantity_after_loss = quantity * (1 - self.data_store.heat_transfer_loss_per_side)
        return Trade(Action.SELL, Resource.HEATING, quantity_after_loss, price, self.guid, False, market, period,
                     self.data_store.heat_transfer_loss_per_side)

    def construct_buy_heat_trade(self, quantity_needed: float, price: float, market: Market,
                                 period: datetime.datetime) -> Trade:
        # The heat transfer loss needs to be accounted for
        quantity_to_buy = quantity_needed / (1 - self.data_store.heat_transfer_loss_per_side)
        return Trade(Action.BUY, Resource.HEATING, quantity_to_buy, price, self.guid, False, market, period,
                     self.data_store.heat_transfer_loss_per_side)

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
