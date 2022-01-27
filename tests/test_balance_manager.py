import datetime
import math
from unittest import TestCase

from tradingplatformpoc.balance_manager import calculate_costs
from tradingplatformpoc.bid import Action, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.trade import Market, Trade


SOME_DATETIME = datetime.datetime(2019, 1, 2)


class Test(TestCase):

    def test_calculate_costs_local_surplus_becomes_deficit(self):
        """
        Expected: Locally produced electricity covers local demand exactly, so clearing price gets set to 0.5.
        Actual: Locally produced electricity didn't cover local demand, external electricity needed to be imported (200
            kWh) at a higher price (1.0) than the local clearing price. Extra cost of (1-0.5)*200=100 need to be
            distributed.
        """
        bids = [BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, 0.5, "Seller1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, False),
                BidWithAcceptanceStatus(Action.SELL, Resource.HEATING, 10000, 2, "Grid", True, True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 1990, 0.5, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 2100, 0.5, "Buyer1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 90, 0.5, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.SELL, Resource.ELECTRICITY, 200, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        costs = calculate_costs(bids, trades, 0.5, 0.5)
        self.assertAlmostEqual(4.545, costs["Seller1"], places=3)
        self.assertAlmostEqual(90.909, costs["Buyer1"], places=3)
        self.assertAlmostEqual(4.545, costs["Buyer2"], places=3)

    def test_calculate_costs_no_extra(self):
        """
        Expected: Local deficit, so clearing price gets set to 1.0.
        Actual: Local deficit a bit larger than expected. But import price = local price, so no extra cost.
        """
        bids = [BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 100, 0.5, "Seller1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.HEATING, 10000, 2, "Grid", True, True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 80, 1, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 200, 1, "Buyer1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.SELL, Resource.ELECTRICITY, 120, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        costs = calculate_costs(bids, trades, 1, 0.5)
        self.assertAlmostEqual(0, costs["Seller1"], places=3)
        self.assertAlmostEqual(0, costs["Buyer1"], places=3)

    def test_calculate_costs_local_deficit_becomes_surplus(self):
        """
        Expected: Locally produced electricity won't cover local demand, so clearing price gets set to 1.0.
        Actual: Locally produced electricity does cover local demand, surplus needs to be exported (100 kWh) at a lower
            price (0.5) than the local clearing price. Loss of revenue (1-0.5)*100=50 need to be distributed.
        """
        bids = [BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, 0.5, "Seller1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.HEATING, 10000, 2, "Grid", True, True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 2000, 1, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 1800, 1, "Buyer1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        costs = calculate_costs(bids, trades, 1.0, 0.5)
        self.assertAlmostEqual(0, costs["Seller1"], places=3)
        self.assertAlmostEqual(50, costs["Buyer1"], places=3)
        self.assertAlmostEqual(0, costs["Buyer2"], places=3)

    def test_no_bid_from_seller(self):
        """
        Expected: Locally produced electricity won't cover local demand, so clearing price gets set to 1.0. 'Seller1'
            doesn't anticipate to produce anything, so doesn't make a bid.
        Actual: Locally produced electricity does cover local demand, surplus needs to be exported (100 kWh) at a lower
            price (0.5) than the local clearing price. Loss of revenue (1-0.5)*100=50 need to be distributed.
        """
        bids = [BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.HEATING, 10000, 2, "Grid", True, True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 2000, 1, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 1800, 1, "Buyer1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        costs = calculate_costs(bids, trades, 1.0, 0.5)
        self.assertAlmostEqual(45.4545, costs["Seller1"], places=3)
        self.assertAlmostEqual(4.54545, costs["Buyer1"], places=3)
        self.assertAlmostEqual(0, costs["Buyer2"], places=3)

    def test_2_external_bids(self):
        """
        When there are more than 1 external bid for the same resource, an error should be raised.
        """
        bids = [BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 10000, 1, "Grid", True, True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 2000, 1, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        with self.assertRaises(RuntimeError):
            calculate_costs(bids, trades, 1.0, 0.5)

    def test_different_periods(self):
        """
        When there are trades from more than 1 periods, an error should be raised.
        """
        next_period = datetime.datetime(2019, 1, 2, 1)
        bids = [BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, 0.5, "Seller1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, False)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 1990, 0.5, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 2100, 0.5, "Buyer1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 90, 0.5, "Buyer2", False, Market.LOCAL, next_period),
                  Trade(Action.SELL, Resource.ELECTRICITY, 200, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        with self.assertRaises(RuntimeError):
            calculate_costs(bids, trades, 0.5, 0.5)

    def test_2_external_trades(self):
        """
        When there are more than 1 external trade for the same resource, an error should be raised.
        """
        bids = [BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 2000, 1, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Grid", True, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.SELL, Resource.ELECTRICITY, 100, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        with self.assertRaises(RuntimeError):
            calculate_costs(bids, trades, 1.0, 0.5)

    def test_retail_price_less_than_local(self):
        """
        If the external retail price is lower than the local clearing price, an error should be raised.
        """
        bids = [BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 0.9, "Grid", True, True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 2000, 1, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        with self.assertRaises(RuntimeError):
            calculate_costs(bids, trades, 1.0, 0.5)

    def test_no_external_bid(self):
        """
        If there is no bid from an external grid agent, an error should be raised.
        """
        bids = [BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1.0, "Seller1", False, True)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 2000, 1, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, 1, "Seller1", False, Market.LOCAL, SOME_DATETIME)]
        with self.assertRaises(RuntimeError):
            calculate_costs(bids, trades, 1.0, 0.5)

    def test_2_bids_accepted_for_internal_agent(self):
        """
        Test that when more than 1 bids are accepted, for a single agent in a trading period, an error is thrown
        """
        bids = [BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, 0.5, "Seller1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10, 0.5, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, False)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 1990, 0.5, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 2100, 0.5, "Buyer1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 90, 0.5, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.SELL, Resource.ELECTRICITY, 200, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        with self.assertRaises(RuntimeError):
            calculate_costs(bids, trades, 0.5, 0.5)

    def test_2_trades_for_internal_agent(self):
        """
        Test that when there are more than 1 trades for a single agent in a trading period, an error is thrown
        """
        bids = [BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, 0.5, "Seller1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1", False, True),
                BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, True),
                BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, False)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 1990, 0.5, "Seller1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 2100, 0.5, "Buyer1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.SELL, Resource.ELECTRICITY, 100, 0.5, "Buyer1", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.BUY, Resource.ELECTRICITY, 90, 0.5, "Buyer2", False, Market.LOCAL, SOME_DATETIME),
                  Trade(Action.SELL, Resource.ELECTRICITY, 200, 1, "Grid", True, Market.LOCAL, SOME_DATETIME)]
        with self.assertRaises(RuntimeError):
            calculate_costs(bids, trades, 0.5, 0.5)
