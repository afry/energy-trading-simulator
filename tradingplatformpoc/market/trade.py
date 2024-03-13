import datetime
from enum import Enum

from tradingplatformpoc.market.bid import Action, Resource


class Market(Enum):
    LOCAL = 0
    EXTERNAL = 1


class TradeMetadataKey(Enum):
    STORAGE_LEVEL = 0
    HEAT_PUMP_WORKLOAD = 1
    BATTERY_LEVEL = 2
    ACC_TANK_LEVEL = 3
    HP_HIGH_HEAT_PROD = 4
    HP_LOW_HEAT_PROD = 5
    CM_PROD = 6  # Cooling machine
    # Building inertia as thermal energy storage things:
    SHALLOW_STORAGE_REL = 7
    DEEP_STORAGE_REL = 8
    SHALLOW_STORAGE_ABS = 9
    DEEP_STORAGE_ABS = 10
    SHALLOW_CHARGE = 11
    SHALLOW_DISCHARGE = 12
    FLOW_SHALLOW_TO_DEEP = 13
    SHALLOW_LOSS = 14
    DEEP_LOSS = 15


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
        price: The _net_ price in SEK/kWh (i.e. after including tax and grid fees, if applicable)
        source: String specifying which entity that did the trade (used for debugging)
        by_external: True if trade is made by an external grid agent, False otherwise. Needed for example when
            calculating extra cost distribution in balance_manager
        market: LOCAL or EXTERNAL (agents can decide to buy/sell directly to external grids)
        period: What period the trade happened
        loss: Loss of the resource (between 0, inclusive, and 1, defaults to 0)
        tax_paid: Tax, in SEK/kWh, that the "source" pays for this trade. Sellers pay the tax so this will be 0 for all
            BUY-trades
        grid_fee_paid: Grid fee, in SEK/kWh, that the "source" pays for this trade. Will be 0 for trades made by a
            GridAgent, since anything else would mean that they would "pay to themselves" essentially
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
    tax_paid: float
    grid_fee_paid: float

    def __init__(self, period: datetime.datetime, action: Action, resource: Resource, quantity: float, price: float,
                 source: str, by_external: bool, market: Market, loss: float = 0.0, tax_paid: float = 0.0,
                 grid_fee_paid: float = 0.0):
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
        self.tax_paid = tax_paid
        self.grid_fee_paid = grid_fee_paid

    def __str__(self):
        return "{},{},{},{},{},{},{},{},{},{},{}".format(self.period,
                                                         self.source,
                                                         self.by_external,
                                                         self.action.name,
                                                         self.resource.name,
                                                         self.market.name,
                                                         self.quantity_pre_loss,
                                                         self.quantity_post_loss,
                                                         self.price,
                                                         self.tax_paid,
                                                         self.grid_fee_paid)

    def to_dict(self) -> dict:
        """Same function name as the one in BidWithAcceptanceStatus, so that the same method can be reused."""
        return {'period': self.period,
                'source': self.source,
                'by_external': self.by_external,
                'action': self.action,
                'resource': self.resource,
                'market': self.market,
                'quantity_pre_loss': self.quantity_pre_loss,
                'quantity_post_loss': self.quantity_post_loss,
                'price': self.price,
                'tax_paid': self.tax_paid,
                'grid_fee_paid': self.grid_fee_paid}

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

    def get_total_grid_fee_paid(self) -> float:
        """
        Paid by seller, and the seller gets paid for the quantity after losses
        """
        if self.action == Action.BUY:
            return 0.0
        else:
            return self.quantity_post_loss * self.grid_fee_paid

    def get_total_tax_paid(self) -> float:
        """
        Paid by seller, and the seller gets paid for the quantity after losses
        """
        if self.action == Action.BUY:
            return 0.0
        else:
            return self.quantity_post_loss * self.tax_paid
