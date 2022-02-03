import logging
import datetime
from enum import Enum
from typing import Iterable


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


class Bid:
    """The bid model for our trading tradingplatformpoc.

    Parameters:
        action: Buy/sell
        resource: Electricity
        quantity: Amount in kWh
        price: SEK/kWh
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

    def __init__(self, action: Action, resource: Resource, quantity: float, price: float, source: str,
                 by_external: bool):
        if quantity <= 0:
            logger.warning("Creating bid with quantity {}! Source was '{}'".format(quantity, source))
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price
        self.source = source
        self.by_external = by_external


class BidWithAcceptanceStatus(Bid):
    """
    A bid, with the additional information of whether the bid was accepted or not, in the market clearing process.
    """
    was_accepted: bool

    def __init__(self, action: Action, resource: Resource, quantity: float, price: float, source: str,
                 by_external: bool, was_accepted: bool):
        super().__init__(action, resource, quantity, price, source, by_external)
        self.was_accepted = was_accepted

    @staticmethod
    def from_bid(bid: Bid, was_accepted: bool):
        return BidWithAcceptanceStatus(bid.action, bid.resource, bid.quantity, bid.price, bid.source, bid.by_external,
                                       was_accepted)

    def to_string_with_period(self, period: datetime.datetime):
        return "{},{},{},{},{},{},{},{}".format(period,
                                                self.source,
                                                self.by_external,
                                                action_string(self.action),
                                                resource_string(self.resource),
                                                self.quantity,
                                                self.price,
                                                self.was_accepted)


def write_rows(bids_with_acceptance_status: Iterable[BidWithAcceptanceStatus], period: datetime.datetime) -> str:
    full_string = ""
    for bid in bids_with_acceptance_status:
        full_string = full_string + bid.to_string_with_period(period) + "\n"
    return full_string
