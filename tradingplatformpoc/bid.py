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
        self.was_accepted = None

    def set_was_accepted(self, was_accepted: bool):
        self.was_accepted = was_accepted


class Action:
    BUY = 0
    SELL = 1


class Resource:
    ELECTRICITY = 0
    HEATING = 1
    COOLING = 2
