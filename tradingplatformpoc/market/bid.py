import datetime
import logging
from enum import Enum
from typing import Iterable


class Action(Enum):
    BUY = 0
    SELL = 1


class Resource(Enum):
    ELECTRICITY = 0
    HEATING = 1  # TODO: remove
    COOLING = 2
    LOW_TEMP_HEAT = 3  # ~40 degrees Celsius - can cover space heating demand
    HIGH_TEMP_HEAT = 4  # ~65 degrees Celsius - needed for hot water, but can also cover space heating

    def get_display_name(self) -> str:
        if self.name == 'LOW_TEMP_HEAT':
            return 'low-temp heat'
        elif self.name == 'HIGH_TEMP_HEAT':
            return 'high-temp heat'
        return self.name.lower()

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


logger = logging.getLogger(__name__)


class GrossBid:
    """The bid model for our trading platform.

    Parameters:
        period: time bid occurred
        action: Buy/sell
        resource: Electricity
        quantity: Amount in kWh
        price: The _gross_ price in SEK/kWh
        source: String specifying which entity created the bid (used for debugging)
        by_external: True if bid is made by an external grid agent, False otherwise. Needed for example when calculating
            extra cost distribution in balance_manager
    """
    period: datetime.datetime
    action: Action
    resource: Resource
    quantity: float
    price: float
    source: str
    by_external: bool

    def __init__(self, period: datetime.datetime, action: Action, resource: Resource, quantity: float, price: float,
                 source: str, by_external: bool):
        if quantity <= 0:
            logger.warning("Creating bid with quantity {}! Source was '{}'".format(quantity, source))
        self.period = period
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price
        self.source = source
        self.by_external = by_external
        

class NetBid(GrossBid):

    def __init__(self, period: datetime.datetime, action: Action, resource: Resource, quantity: float, price: float,
                 source: str, by_external: bool):
        super().__init__(period, action, resource, quantity, price, source, by_external)

    @staticmethod
    def from_gross_bid(gross_bid: GrossBid, net_price: float):
        return NetBid(gross_bid.period, gross_bid.action, gross_bid.resource, gross_bid.quantity, net_price,
                      gross_bid.source, gross_bid.by_external)


class NetBidWithAcceptanceStatus(NetBid):
    """
    A bid, with the additional information of how much of the bid was accepted, in the market clearing process.
    """
    accepted_quantity: float

    def __init__(self, period: datetime.datetime, action: Action, resource: Resource, quantity: float, price: float,
                 source: str, by_external: bool, accepted_quantity: float):
        super().__init__(period, action, resource, quantity, price, source, by_external)
        self.accepted_quantity = accepted_quantity

    @staticmethod
    def from_bid(bid: NetBid, accepted_quantity: float):
        return NetBidWithAcceptanceStatus(bid.period, bid.action, bid.resource, bid.quantity, bid.price, bid.source,
                                          bid.by_external, accepted_quantity)

    def to_string(self) -> str:
        return "{},{},{},{},{},{},{},{}".format(self.period,
                                                self.source,
                                                self.by_external,
                                                self.action.name,
                                                self.resource.name,
                                                self.quantity,
                                                self.price,
                                                self.accepted_quantity)

    def to_dict(self) -> dict:
        """Same function name as the one in Trade, so that the same method can be reused."""
        return {'period': self.period,
                'source': self.source,
                'by_external': self.by_external,
                'action': self.action,
                'resource': self.resource,
                'quantity': self.quantity,
                'price': self.price,
                'accepted_quantity': self.accepted_quantity}


def write_bid_rows(bids_with_acceptance_status: Iterable[NetBidWithAcceptanceStatus]) -> str:
    full_string = ""
    for bid in bids_with_acceptance_status:
        full_string = full_string + bid.to_string() + "\n"
    return full_string
