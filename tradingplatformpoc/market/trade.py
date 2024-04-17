import datetime
from enum import Enum
from typing import List


class Market(Enum):
    LOCAL = 0
    EXTERNAL = 1


class Resource(Enum):
    ELECTRICITY = 0
    COOLING = 2
    LOW_TEMP_HEAT = 3  # ~40 degrees Celsius - can cover space heating demand
    HIGH_TEMP_HEAT = 4  # ~65 degrees Celsius - needed for hot water, but can also cover space heating

    def get_display_name(self, capitalized: bool = False) -> str:
        un_capitalized: str
        if self.name == 'LOW_TEMP_HEAT':
            un_capitalized = 'low-temp heat'
        elif self.name == 'HIGH_TEMP_HEAT':
            un_capitalized = 'high-temp heat'
        else:
            un_capitalized = self.name.lower()
        return un_capitalized.capitalize() if capitalized else un_capitalized

    @staticmethod
    def is_resource_name(a_string: str, case_sensitive: bool = True) -> bool:
        for res in Resource:
            if (a_string == res.name) or (not case_sensitive and (a_string.lower() == res.name.lower())):
                return True
        return False

    @staticmethod
    def from_string(a_string: str):
        for res in Resource:
            if a_string.lower() == res.name.lower():
                return res
        raise RuntimeError('No resource with name ' + a_string)


class Action(Enum):
    BUY = 0
    SELL = 1


class TradeMetadataKey(Enum):
    BATTERY_LEVEL = 2
    ACC_TANK_LEVEL = 3
    HP_HIGH_HEAT_PROD = 4
    HP_LOW_HEAT_PROD = 5
    HP_COOL_PROD = 6
    # Building inertia as thermal energy storage things:
    SHALLOW_STORAGE_REL = 7
    DEEP_STORAGE_REL = 8
    SHALLOW_STORAGE_ABS = 9
    DEEP_STORAGE_ABS = 10
    SHALLOW_CHARGE = 11
    FLOW_SHALLOW_TO_DEEP = 13
    SHALLOW_LOSS = 14
    DEEP_LOSS = 15

    HEAT_DUMP = 16
    COOL_DUMP = 17

    # Cooling machine
    CM_COOL_PROD = 18
    CM_HEAT_PROD = 19
    CM_ELEC_CONS = 20


class Trade:
    """
    The Trade class is used to keep track of energy trades that have taken place
    Costs are calculated on the quantity before losses (see objective function in Chalmers' code).

    Parameters:
        action: Buy or sell
        resource: Electricity or heating
        quantity: Amount in kWh (before any losses)
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


def combine_trades(trades: List[Trade]) -> Trade:
    """Combines trades made in the same period, for the same resource etc into one."""
    if not trades:
        raise ValueError("List of trades is empty")

    resource = trades[0].resource
    by_external = trades[0].by_external
    market = trades[0].market
    period = trades[0].period
    price = trades[0].price
    source = trades[0].source
    for trade in trades[1:]:
        if trade.resource != resource:
            raise ValueError("Resource field is not identical across all trades")
        if trade.by_external != by_external:
            raise ValueError("by_external field is not identical across all trades")
        if trade.market != market:
            raise ValueError("Market field is not identical across all trades")
        if trade.period != period:
            raise ValueError("Period field is not identical across all trades")
        if trade.price != price:
            raise ValueError("Price field is not identical across all trades")
        if trade.source != source:
            raise ValueError("Source field is not identical across all trades")

    quantity_pre_loss = sum(trade.quantity_pre_loss * (1.0 if trade.action == Action.BUY else -1.0)
                            for trade in trades)
    quantity_post_loss = sum(trade.quantity_post_loss * (1.0 if trade.action == Action.BUY else -1.0)
                             for trade in trades)
    loss = 1 - (quantity_post_loss / quantity_pre_loss)
    tax_paid = sum(trade.tax_paid for trade in trades)
    grid_fee_paid = sum(trade.grid_fee_paid for trade in trades)

    action = Action.BUY if quantity_pre_loss > 0 else Action.SELL
    quantity = quantity_pre_loss if quantity_pre_loss > 0 else -quantity_pre_loss

    return Trade(period, action, resource, quantity, price, source, by_external, market,
                 loss, tax_paid, grid_fee_paid)
