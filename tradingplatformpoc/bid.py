import datetime
import logging
from enum import Enum
from typing import Iterable, Optional


class Action(Enum):
    BUY = 0
    SELL = 1


class Resource(Enum):
    ELECTRICITY = 0
    HEATING = 1
    COOLING = 2


logger = logging.getLogger(__name__)


def action_string(action: Action) -> str:
    return "BUY" if action == Action.BUY else "SELL"


def resource_string(resource: Resource) -> str:
    return "ELECTRICITY" if resource == Resource.ELECTRICITY else \
        ("HEATING" if resource == Resource.HEATING else "COOLING")


class GrossBid:
    """The bid model for our trading tradingplatformpoc.

    Parameters:
        action: Buy/sell
        resource: Electricity
        quantity: Amount in kWh
        price: The _gross_ price in SEK/kWh
        co2_intensity: An estimate of gram CO2-equivalents per kWh (of quantity to be sold)
        source: String specifying which entity created the bid (used for debugging)
        by_external: True if bid is made by an external grid agent, False otherwise. Needed for example when calculating
            extra cost distribution in balance_manager
    """
    action: Action
    resource: Resource
    quantity: float
    price: float
    source: str
    by_external: bool
    co2_intensity: Optional[float]

    def __init__(self, action: Action, resource: Resource, quantity: float, price: float,
                 source: str, by_external: bool, co2_intensity: Optional[float] = None):
        if quantity <= 0:
            logger.warning("Creating bid with quantity {}! Source was '{}'".format(quantity, source))
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price
        self.source = source
        self.by_external = by_external
        self.co2_intensity = self._validate_co2_intensity(co2_intensity, action)

    def _validate_co2_intensity(self, co2_intensity: Optional[float], action: Action) -> Optional[float]:
        if (action == Action.BUY) and (co2_intensity is not None):
            raise ValueError("Current action is BUY, so CO2 intensity should be "
                             "None, but found {}.".format(co2_intensity))
        if (action == Action.SELL) and ((co2_intensity is None) or (co2_intensity < 0)):
            raise ValueError("Current action is SELL, so CO2 intensity should be "
                             "non-negative float, but found {}.".format(co2_intensity))
        return co2_intensity


class NetBid(GrossBid):

    def __init__(self, action: Action, resource: Resource, quantity: float, price: float, source: str,
                 by_external: bool, co2_intensity: Optional[float]):
        super().__init__(action, resource, quantity, price, source, by_external, co2_intensity)

    @staticmethod
    def from_gross_bid(gross_bid: GrossBid, net_price: float):
        return NetBid(gross_bid.action, gross_bid.resource, gross_bid.quantity, net_price, gross_bid.source,
                      gross_bid.by_external, gross_bid.co2_intensity)


class NetBidWithAcceptanceStatus(NetBid):
    """
    A bid, with the additional information of how much of the bid was accepted, in the market clearing process.
    """
    accepted_quantity: float

    def __init__(self, action: Action, resource: Resource, quantity: float, price: float, source: str,
                 by_external: bool, co2_intensity: Optional[float], accepted_quantity: float):
        super().__init__(action, resource, quantity, price, source, by_external, co2_intensity)
        self.accepted_quantity = accepted_quantity

    @staticmethod
    def from_bid(bid: NetBid, accepted_quantity: float):
        return NetBidWithAcceptanceStatus(bid.action, bid.resource, bid.quantity, bid.price, bid.source,
                                          bid.by_external, bid.co2_intensity, accepted_quantity)

    def to_string_with_period(self, period: datetime.datetime) -> str:
        return "{},{},{},{},{},{},{},{},{}".format(period,
                                                   self.source,
                                                   self.by_external,
                                                   action_string(self.action),
                                                   resource_string(self.resource),
                                                   self.quantity,
                                                   self.price,
                                                   self.co2_intensity,
                                                   self.accepted_quantity)

    def to_dict_with_period(self, period: datetime.datetime) -> dict:
        """Same function name as the one in Trade, so that the same method can be reused."""
        return {'period': period,
                'source': self.source,
                'by_external': self.by_external,
                'action': self.action,
                'resource': self.resource,
                'quantity': self.quantity,
                'price': self.price,
                'co2_intensity': self.co2_intensity,
                'accepted_quantity': self.accepted_quantity}


def write_bid_rows(bids_with_acceptance_status: Iterable[NetBidWithAcceptanceStatus], period: datetime.datetime) -> str:
    full_string = ""
    for bid in bids_with_acceptance_status:
        full_string = full_string + bid.to_string_with_period(period) + "\n"
    return full_string
