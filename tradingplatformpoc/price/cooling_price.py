from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.price.iprice import IPrice


class CoolingPrice(IPrice):

    def __init__(self):
        super().__init__(Resource.COOLING)
