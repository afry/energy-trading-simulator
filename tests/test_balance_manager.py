import math
from unittest import TestCase

from tradingplatformpoc.balance_manager import calculate_costs
from tradingplatformpoc.bid import Bid, Action, Resource
from tradingplatformpoc.trade import Trade, Market


class Test(TestCase):

    def test_calculate_costs_1(self):
        """
        Expected: Locally produced electricity covers local demand exactly, so clearing price gets set to 0.5.
        Actual: Locally produced electricity didn't cover local demand, external electricity needed to be imported (200
            kWh) at a higher price (1.0) than the local clearing price. Extra cost of (1-0.5)*200=100 need to be
            distributed.
        """
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 2000, 0.5, "Seller1", False),
                Bid(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1", False),
                Bid(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False),
                Bid(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 1990, 0.5, "Seller1", False, Market.LOCAL, None),
                  Trade(Action.BUY, Resource.ELECTRICITY, 2100, math.inf, "Buyer1", False, Market.LOCAL, None),
                  Trade(Action.BUY, Resource.ELECTRICITY, 90, math.inf, "Buyer2", False, Market.LOCAL, None),
                  Trade(Action.SELL, Resource.ELECTRICITY, 200, 1, "Grid", True, Market.LOCAL, None)]
        calculate_costs(bids, trades, 0.5)

    def test_calculate_costs_2(self):
        """
        Expected: Local deficit, so clearing price gets set to 1.0.
        Actual: Local deficit a bit larger than expected. But import price = local price, so no extra cost.
        """
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 100, 0.5, "Seller1", False),
                Bid(Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1", False),
                Bid(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 80, 0.5, "Seller1", False, Market.LOCAL, None),
                  Trade(Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1", False, Market.LOCAL, None),
                  Trade(Action.SELL, Resource.ELECTRICITY, 120, 1, "Grid", True, Market.LOCAL, None)]
        calculate_costs(bids, trades, 1)
