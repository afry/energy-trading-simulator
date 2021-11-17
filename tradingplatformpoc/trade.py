from tradingplatformpoc.bid import Action, Resource


class Trade:
    """The Trade class is used to keep track of energy trades that have taken place

    Parameters:
        action: Buy/sell
        resource: Electricity
        quantity: Amount in kWh
        price: SEK/kWh
        source: String specifying which entity that did the trade (used for debugging)
        market: LOCAL or EXTERNAL (agents can decide to buy/sell directly to external grids)
        period: What period the trade happened
    """

    def __init__(self, action, resource, quantity, price, source, market, period):
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price
        self.source = source
        self.market = market
        self.period = period

    def __str__(self):
        return "{},{},{},{},{},{},{}".format(self.period,
                                             self.source,
                                             action_string(self.action),
                                             resource_string(self.resource),
                                             market_string(self.market),
                                             self.quantity,
                                             self.price)


class Market:
    LOCAL = 0
    EXTERNAL = 1


def market_string(market):
    return "LOCAL" if market == Market.LOCAL else "EXTERNAL"


def action_string(action):
    return "BUY" if action == Action.BUY else "SELL"


def resource_string(resource):
    return "ELECTRICITY" if resource == Resource.ELECTRICITY else \
        ("HEATING" if resource == Resource.HEATING else "COOLING")


def write_rows(trades):
    full_string = ""
    for trade in trades:
        full_string = full_string + str(trade) + "\n"
    return full_string


