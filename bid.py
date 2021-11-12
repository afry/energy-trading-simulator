class Bid:
    """The bid model for our trading platform.

    Parameters:
        action: Buy/sell
        resource: Electricity
        quantity: Amount in kWh
        price: SEK/kWh
        source: String specifying which entity created the bid (used for debugging)
    """

    def __init__(self, action, resource, quantity, price, source):
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price
        self.source = source


class Action:
    BUY = 0
    SELL = 1


class Resource:
    ELECTRICITY = 0
    HEATING = 1
    COOLING = 2
