import datetime
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Union

import numpy as np


from ..market.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from ..market.trade import Market, Trade, TradeMetadataKey


class IAgent(ABC):
    """Interface for agents to implement"""

    guid: str

    def __init__(self, guid: str):
        self.guid = guid

    @abstractmethod
    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None]) -> List[GrossBid]:
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
                                         accepted_bids_for_agent: List[NetBidWithAcceptanceStatus]) -> \
            Tuple[List[Trade], Dict[TradeMetadataKey, Any]]:
        """
        Once market solver has decided a clearing price for each resource, it will send them to the agents with this
        method.
        @return: A tuple: 1. Some trades - but not more than 1 per resource. 2. Metadata
        """
        pass

    def construct_elec_bid(self, action: Action, quantity: float, price: float) -> GrossBid:
        return GrossBid(action, Resource.ELECTRICITY, quantity, price, self.guid, False)

    def construct_sell_heat_bid(self, quantity: float, price: float,
                                heat_transfer_loss_per_side: float) -> GrossBid:
        # Heat transfer loss added
        quantity_after_loss = quantity * (1 - heat_transfer_loss_per_side)
        return GrossBid(Action.SELL, Resource.HEATING, quantity_after_loss, price, self.guid, False)

    def construct_buy_heat_bid(self, quantity_needed: float, price: float,
                               heat_transfer_loss_per_side: float) -> GrossBid:
        # The heat transfer loss needs to be accounted for
        quantity_to_buy = quantity_needed / (1 - heat_transfer_loss_per_side)
        return GrossBid(Action.BUY, Resource.HEATING, quantity_to_buy, price, self.guid, False)

    def construct_elec_trade(self, action: Action, quantity: float, price: float, market: Market,
                             period: datetime.datetime, tax_paid: float = 0.0, grid_fee_paid: float = 0.0) -> Trade:
        return Trade(action, Resource.ELECTRICITY, quantity, price, self.guid, False, market, period, tax_paid=tax_paid,
                     grid_fee_paid=grid_fee_paid)

    def construct_sell_heat_trade(self, quantity: float, price: float, market: Market, period: datetime.datetime,
                                  heat_transfer_loss_per_side: float) -> \
            Trade:
        # Heat transfer loss added
        quantity_after_loss = quantity * (1 - heat_transfer_loss_per_side)
        return Trade(Action.SELL, Resource.HEATING, quantity_after_loss, price, self.guid, False, market, period,
                     loss=heat_transfer_loss_per_side)

    def construct_buy_heat_trade(self, quantity_needed: float, price: float, market: Market,
                                 period: datetime.datetime, heat_transfer_loss_per_side: float) -> Trade:
        # The heat transfer loss needs to be accounted for
        quantity_to_buy = quantity_needed / (1 - heat_transfer_loss_per_side)
        return Trade(Action.BUY, Resource.HEATING, quantity_to_buy, price, self.guid, False, market, period,
                     loss=heat_transfer_loss_per_side)


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
