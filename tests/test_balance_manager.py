import math
from unittest import TestCase

from tradingplatformpoc.balance_manager import calculate_costs
from tradingplatformpoc.bid import Bid, Action, Resource
from tradingplatformpoc.trade import Trade, Market


class Test(TestCase):
    def test_calculate_costs(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 2000, 0.5, "Seller1"),
                Bid(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1"),
                Bid(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2"),
                Bid(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid")]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 1990, 0.5, "Seller1", Market.LOCAL, None),
                  Trade(Action.BUY, Resource.ELECTRICITY, 2100, math.inf, "Buyer1", Market.LOCAL, None),
                  Trade(Action.BUY, Resource.ELECTRICITY, 90, math.inf, "Buyer2", Market.LOCAL, None),
                  Trade(Action.SELL, Resource.ELECTRICITY, 200, 1, "Grid", Market.LOCAL, None)]
        calculate_costs(bids, trades, 0.5)
