import datetime
from enum import Enum

import pandas as pd

from tradingplatformpoc.bid import Action, Resource, action_string, resource_string


class Market(Enum):
    LOCAL = 0
    EXTERNAL = 1


class TradeMetadataKey(Enum):
    STORAGE_LEVEL = 0
    HEAT_PUMP_WORKLOAD = 1


class Trade:
    """
    The Trade class is used to keep track of energy trades that have taken place

    These fields are used to calculate the cost of a trade:
    quantity_pre_loss: Amount in kWh, before any losses are taken into account
    quantity_post_loss: Amount in kWh, after losses are taken into account
    For BUY-trades, the buyer pays for the quantity before losses.
    For SELL-trades, the seller gets paid for the quantity after losses.

    Parameters:
        action: Buy or sell
        resource: Electricity or heating
        quantity: Amount in kWh (before any losses are taken into account)
        price: SEK/kWh
        source: String specifying which entity that did the trade (used for debugging)
        by_external: True if trade is made by an external grid agent, False otherwise. Needed for example when
            calculating extra cost distribution in balance_manager
        market: LOCAL or EXTERNAL (agents can decide to buy/sell directly to external grids)
        period: What period the trade happened
        loss: Loss of the resource (between 0, inclusive, and 1, defaults to 0)
    """

    action: Action
    resource: Resource
    quantity_pre_loss: float
    quantity_post_loss: float
    price: float
    source: str
    by_external: bool
    market: Market
    period: datetime.datetime

    def __init__(self, action: Action, resource: Resource, quantity: float, price: float, source: str,
                 by_external: bool, market: Market, period: datetime.datetime, loss: float = 0.0):
        if quantity <= 0:
            raise RuntimeError('Trade must have quantity > 0, but was ' + str(quantity))
        if loss < 0 or loss >= 1:
            raise RuntimeError('Trade must have 0 <= loss < 1, but was ' + str(loss))
        self.action = action
        self.resource = resource
        self.quantity_pre_loss = quantity
        self.quantity_post_loss = quantity * (1 - loss)
        self.price = price
        self.source = source
        self.by_external = by_external
        self.market = market
        self.period = period

    def __str__(self):
        return "{},{},{},{},{},{},{},{},{}".format(self.period,
                                                   self.source,
                                                   self.by_external,
                                                   action_string(self.action),
                                                   resource_string(self.resource),
                                                   market_string(self.market),
                                                   self.quantity_pre_loss,
                                                   self.quantity_post_loss,
                                                   self.price)

    def to_series_with_period(self, period: datetime.datetime) -> pd.Series:
        """Same function name as the one in BidWithAcceptanceStatus, so that the same method can be reused."""
        return pd.Series(data={'period': self.period,
                               'source': self.source,
                               'by_external': self.by_external,
                               'action': self.action,
                               'resource': self.resource,
                               'market': self.market,
                               'quantity_pre_loss': self.quantity_pre_loss,
                               'quantity_post_loss': self.quantity_post_loss,
                               'price': self.price})

    def get_cost_of_trade(self) -> float:
        """
        Negative if it is an income, i.e. if the trade is a SELL.
        For BUY-trades, the buyer pays for the quantity before losses.
        For SELL-trades, the seller gets paid for the quantity after losses.
        """
        if self.action == Action.BUY:
            return self.quantity_pre_loss * self.price
        else:
            return -self.quantity_post_loss * self.price


def market_string(market: Market) -> str:
    return "LOCAL" if market == Market.LOCAL else "EXTERNAL"
