from enum import Enum


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

    def __init__(self, action, resource, quantity, price, source, by_external):
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

    def __init__(self, action, resource, quantity, price, source, by_external, was_accepted: bool):
        super().__init__(action, resource, quantity, price, source, by_external)
        self.was_accepted = was_accepted

    @staticmethod
    def from_bid(bid: Bid, was_accepted: bool):
        return BidWithAcceptanceStatus(bid.action, bid.resource, bid.quantity, bid.price, bid.source, bid.by_external,
                                       was_accepted)


class Action(Enum):
    BUY = 0
    SELL = 1


class Resource(Enum):
    ELECTRICITY = 0
    HEATING = 1
    COOLING = 2
