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
    """The Trade class is used to keep track of energy trades that have taken place

    Parameters:
        action: Buy or sell
        resource: Electricity or heating
        quantity: Amount in kWh
        price: The _net_ price in SEK/kWh
        source: String specifying which entity that did the trade (used for debugging)
        by_external: True if trade is made by an external grid agent, False otherwise. Needed for example when
            calculating extra cost distribution in balance_manager
        market: LOCAL or EXTERNAL (agents can decide to buy/sell directly to external grids)
        period: What period the trade happened
        tax_paid: Tax, in SEK/kWh, that the "source" pays for this trade. Sellers pay the tax so this will be 0 for all
            BUY-trades
        grid_fee_paid: Grid fee, in SEK/kWh, that the "source" pays for this trade. Will be 0 for trades made by a
            GridAgent, since anything else would mean that they would "pay to themselves" essentially
    """

    action: Action
    resource: Resource
    quantity: float
    price: float
    source: str
    by_external: bool
    market: Market
    period: datetime.datetime
    tax_paid: float
    grid_fee_paid: float

    def __init__(self, action: Action, resource: Resource, quantity: float, price: float, source: str,
                 by_external: bool, market: Market, period: datetime.datetime, tax_paid: float = 0.0,
                 grid_fee_paid: float = 0.0):
        if quantity <= 0:
            raise RuntimeError('Trade must have quantity > 0, but was ' + str(quantity))
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price
        self.source = source
        self.by_external = by_external
        self.market = market
        self.period = period

    def __str__(self):
        return "{},{},{},{},{},{},{},{},{},{}".format(self.period,
                                                      self.source,
                                                      self.by_external,
                                                      action_string(self.action),
                                                      resource_string(self.resource),
                                                      market_string(self.market),
                                                      self.quantity,
                                                      self.price,
                                                      self.tax_paid,
                                                      self.grid_fee_paid)

    def to_series_with_period(self, period: datetime.datetime) -> pd.Series:
        """Same function name as the one in BidWithAcceptanceStatus, so that the same method can be reused."""
        return pd.Series(data={'period': self.period,
                               'source': self.source,
                               'by_external': self.by_external,
                               'action': self.action,
                               'resource': self.resource,
                               'market': self.market,
                               'quantity': self.quantity,
                               'price': self.price,
                               'tax_paid': self.tax_paid,
                               'grid_fee_paid': self.grid_fee_paid})


def market_string(market: Market) -> str:
    return "LOCAL" if market == Market.LOCAL else "EXTERNAL"
