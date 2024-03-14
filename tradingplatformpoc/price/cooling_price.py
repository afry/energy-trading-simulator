from tradingplatformpoc.market.trade import Resource
from tradingplatformpoc.price.iprice import IPrice


class CoolingPrice(IPrice):

    def __init__(self):
        super().__init__(Resource.COOLING)
