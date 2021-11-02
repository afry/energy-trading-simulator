class Bid:
    """The bid model for our trading platform.

    Parameters:
        action: Buy/sell
        resource: Electricity
        quantity: Amount in kWh
        price: SEK/kWh
    """

    def __init__(self, action, resource, quantity, price):
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price


class Action:
    BUY = 0
    SELL = 1


class Resource:
    ELECTRICITY = 0
    HEATING = 1
    COOLING = 2
