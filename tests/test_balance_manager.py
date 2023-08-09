import datetime
import math
from unittest import TestCase, mock

import numpy as np

import pandas as pd

import pytz

from tradingplatformpoc.market.balance_manager import calculate_penalty_costs_for_period_and_resource, \
    correct_for_exact_heating_price
from tradingplatformpoc.market.bid import Action, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Market, Trade


class TestBalanceManager(TestCase):
    some_datetime = datetime.datetime(2019, 1, 2, tzinfo=pytz.utc)
    default_heat_wholesale_price = 1.5

    def test_calculate_costs_local_surplus_becomes_deficit(self):
        """
        Expected: Locally produced electricity covers local demand exactly, so clearing price gets set to 0.5.
        Actual: Locally produced electricity didn't cover local demand, external electricity needed to be imported (200
            kWh) at a higher price (1.0) than the local clearing price. Extra cost of (1-0.5)*200=100 need to be
            distributed.
        """
        ws_price = 0.5
        ret_price = 1
        bids = [NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 200, ws_price, "Seller", False, 200),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 190, math.inf, "Buyer1", False, 190),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 10, math.inf, "Buyer2", False, 10),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, ret_price, "Grid", True, 0)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 199, ws_price, "Seller", False, Market.LOCAL,
                        self.some_datetime),
                  Trade(Action.BUY, Resource.ELECTRICITY, 210, ws_price, "Buyer1", False, Market.LOCAL,
                        self.some_datetime),
                  Trade(Action.BUY, Resource.ELECTRICITY, 9, ws_price, "Buyer2", False, Market.LOCAL,
                        self.some_datetime),
                  Trade(Action.SELL, Resource.ELECTRICITY, 20, ret_price, "Grid", True, Market.LOCAL,
                        self.some_datetime)]
        costs = calculate_penalty_costs_for_period_and_resource(bids, trades, ws_price, ws_price)
        self.assertAlmostEqual(0.455, costs["Seller"], places=3)
        self.assertAlmostEqual(9.091, costs["Buyer1"], places=3)
        self.assertAlmostEqual(0.455, costs["Buyer2"], places=3)

    def test_calculate_costs_no_extra(self):
        """
        Expected: Local deficit, so clearing price gets set to 1.0.
        Actual: Local deficit a bit larger than expected. But import price = local price, so no extra cost.
        """
        bids = [NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 100, 0.5, "Seller1", False, 100),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1", False, 200),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, 1, "Grid", True, 100)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 80, 1, "Seller1", False, Market.LOCAL, self.some_datetime),
                  Trade(Action.BUY, Resource.ELECTRICITY, 200, 1, "Buyer1", False, Market.LOCAL, self.some_datetime),
                  Trade(Action.SELL, Resource.ELECTRICITY, 120, 1, "Grid", True, Market.LOCAL, self.some_datetime)]
        costs = calculate_penalty_costs_for_period_and_resource(bids, trades, 1.0, 0.5)
        self.assertEqual(0, len(costs))

    def test_calculate_costs_local_deficit_becomes_surplus(self):
        """
        Expected: Locally produced electricity won't cover local demand, so clearing price gets set to the retail price.
        Actual: Locally produced electricity does cover local demand, surplus needs to be exported (100 kWh) at a lower
            price (0.5) than the local clearing price. Loss of revenue (1-0.5)*100=50 need to be distributed.
        """
        ret_price = 1
        ws_price = 0.5
        bids = [NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, ws_price, "Seller1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, ret_price, "Grid", True, 100)]
        trades = [Trade(Action.SELL, Resource.ELECTRICITY, 2000, ret_price, "Seller1", False, Market.LOCAL,
                        self.some_datetime),
                  Trade(Action.BUY, Resource.ELECTRICITY, 1800, ret_price, "Buyer1", False, Market.LOCAL,
                        self.some_datetime),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, ret_price, "Buyer2", False, Market.LOCAL,
                        self.some_datetime),
                  Trade(Action.BUY, Resource.ELECTRICITY, 100, ws_price, "Grid", True, Market.LOCAL,
                        self.some_datetime)]
        # Buyer1 pays 1800*1 = 1800
        # Buyer2 pays 100*1 = 100
        # Grid pays 100*0.5 = 50
        # Seller receives 2000*1 = 2000
        # Discrepancy of 50: 1800+100+50 = 1950 paid in, 2000 paid out. Need 50 more paid in.
        costs = calculate_penalty_costs_for_period_and_resource(bids, trades, ret_price, ws_price)
        self.assertEqual(1, len(costs))
        self.assertAlmostEqual(50, costs["Buyer1"], places=3)

    def test_no_bid_from_seller(self):
        """
        Expected: Locally produced electricity won't cover local demand, so clearing price gets set to 1.0. 'Seller1'
            doesn't anticipate to produce anything, so doesn't make a bid.
        Actual: Locally produced electricity does cover local demand, surplus needs to be exported (100 kWh) at a lower
            price (0.5) than the local clearing price. Loss of revenue (1-0.5)*100=50 need to be distributed.
        """
        rp = 1
        wp = 0.5
        bids = [NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, rp, "Grid", True, 2100)]
        trades = \
            [Trade(Action.SELL, Resource.ELECTRICITY, 2000, rp, "Seller1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 1800, rp, "Buyer1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, rp, "Buyer2", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, rp, "Grid", True, Market.LOCAL, self.some_datetime)]
        costs = calculate_penalty_costs_for_period_and_resource(bids, trades, rp, wp)
        self.assertEqual(2, len(costs))
        self.assertAlmostEqual(45.4545, costs["Seller1"], places=3)
        self.assertAlmostEqual(4.54545, costs["Buyer1"], places=3)

    def test_2_external_bids(self):
        """
        When there are more than 1 external bid for the same resource, an error should be raised.
        """
        rp = 1
        wp = 0.5
        bids = [NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, rp, "Grid", True, 2100),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 10000, rp, "Grid", True, 0)]
        trades = \
            [Trade(Action.SELL, Resource.ELECTRICITY, 2000, rp, "Seller1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, rp, "Buyer2", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, rp, "Grid", True, Market.LOCAL, self.some_datetime)]
        with self.assertRaises(RuntimeError):
            calculate_penalty_costs_for_period_and_resource(bids, trades, rp, wp)

    def test_different_periods(self):
        """
        When there are trades from more than 1 periods, an error should be raised.
        """
        next_period = datetime.datetime(2019, 1, 2, 1)
        rp = 1
        wp = 0.5
        bids = [NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, 0.5, "Seller1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1", False, 1900),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, rp, "Grid", True, 0)]
        trades = \
            [Trade(Action.SELL, Resource.ELECTRICITY, 1990, wp, "Seller1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 2100, wp, "Buyer1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 90, wp, "Buyer2", False, Market.LOCAL, next_period),
             Trade(Action.SELL, Resource.ELECTRICITY, 200, rp, "Grid", True, Market.LOCAL, self.some_datetime)]
        with self.assertRaises(RuntimeError):
            calculate_penalty_costs_for_period_and_resource(bids, trades, wp, wp)

    def test_2_external_trades(self):
        """
        When there are more than 1 external trade for the same resource, an error should be raised.
        """
        rp = 1
        wp = 0.5
        bids = [NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, rp, "Grid", True, 2100)]
        trades = \
            [Trade(Action.SELL, Resource.ELECTRICITY, 2000, rp, "Seller1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, rp, "Buyer2", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, rp, "Grid", True, Market.LOCAL, self.some_datetime),
             Trade(Action.SELL, Resource.ELECTRICITY, 100, rp, "Grid", True, Market.LOCAL, self.some_datetime)]
        with self.assertRaises(RuntimeError):
            calculate_penalty_costs_for_period_and_resource(bids, trades, rp, wp)

    def test_retail_price_less_than_local(self):
        """
        If the external retail price is lower than the local clearing price, an error should be raised.
        """
        rp = 0.9
        wp = 0.5
        lp = 1.0
        bids = [NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, rp, "Grid", True, 2100)]
        trades = \
            [Trade(Action.SELL, Resource.ELECTRICITY, 2000, lp, "Seller1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, lp, "Buyer2", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, lp, "Grid", True, Market.LOCAL, self.some_datetime)]
        with self.assertRaises(RuntimeError):
            calculate_penalty_costs_for_period_and_resource(bids, trades, lp, wp)

    def test_no_external_bid(self):
        """
        If there is no bid from an external grid agent, an error should be raised.
        """
        lp = 1.0
        wp = 0.5
        bids = [NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 2000, math.inf, "Buyer1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, lp, "Seller1", False, 2100)]
        trades = \
            [Trade(Action.SELL, Resource.ELECTRICITY, 2000, lp, "Seller1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, lp, "Buyer2", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 100, lp, "Seller1", False, Market.LOCAL, self.some_datetime)]
        with self.assertRaises(RuntimeError):
            calculate_penalty_costs_for_period_and_resource(bids, trades, lp, wp)

    def test_2_bids_accepted_for_internal_agent(self):
        """
        Test that when more than 1 bids are accepted, for a single agent in a trading period, an error is thrown
        """
        wp = 0.5
        rp = 1
        bids = [NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, wp, "Seller1", False, 1990),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1", False, 1900),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10, wp, "Buyer1", False, 10),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, rp, "Grid", True, 0)]
        trades = \
            [Trade(Action.SELL, Resource.ELECTRICITY, 1990, wp, "Seller1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 2100, wp, "Buyer1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 90, wp, "Buyer2", False, Market.LOCAL, self.some_datetime),
             Trade(Action.SELL, Resource.ELECTRICITY, 200, rp, "Grid", True, Market.LOCAL, self.some_datetime)]
        with self.assertRaises(RuntimeError):
            calculate_penalty_costs_for_period_and_resource(bids, trades, wp, wp)

    def test_2_trades_for_internal_agent(self):
        """
        Test that when there are more than 1 trades for a single agent in a trading period, an error is thrown
        """
        wp = 0.5
        rp = 1
        bids = [NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 2000, wp, "Seller1", False, 2000),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 1900, math.inf, "Buyer1", False, 1900),
                NetBidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, math.inf, "Buyer2", False, 100),
                NetBidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 10000, rp, "Grid", True, 0)]
        trades = \
            [Trade(Action.SELL, Resource.ELECTRICITY, 1990, wp, "Seller1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 2100, wp, "Buyer1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.SELL, Resource.ELECTRICITY, 100, wp, "Buyer1", False, Market.LOCAL, self.some_datetime),
             Trade(Action.BUY, Resource.ELECTRICITY, 90, wp, "Buyer2", False, Market.LOCAL, self.some_datetime),
             Trade(Action.SELL, Resource.ELECTRICITY, 200, rp, "Grid", True, Market.LOCAL, self.some_datetime)]
        with self.assertRaises(RuntimeError):
            calculate_penalty_costs_for_period_and_resource(bids, trades, wp, wp)

    def test_correct_for_exact_heating_price_external_sell(self):
        """
        Test basic functionality of correct_with_exact_heating_price when the external grid sells heating to the
        microgrid.
        The grid will be owed 10 * (0.75 - 0.5) = 2.50 SEK.
        Should be attributed 60% to buyer 1, 40% to buyer 2.
        """
        est_retail_price = 0.5
        exact_retail_price = 0.75
        trades = [
            Trade(Action.SELL, Resource.HEATING, 10, est_retail_price, "Grid", True, Market.LOCAL, self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 6, est_retail_price, "Buyer1", False, Market.LOCAL, self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 4, est_retail_price, "Buyer2", False, Market.LOCAL, self.some_datetime)]

        heating_prices = pd.DataFrame.from_records([{
            'year': self.some_datetime.year,
            'month': self.some_datetime.month,
            'estimated_retail_price': est_retail_price,
            'estimated_wholesale_price': np.nan,
            'exact_retail_price': exact_retail_price,
            'exact_wholesale_price': np.nan}])

        # TODO: Here we use trades, but what is really returned is List[RowProxy]. Fix this?
        with mock.patch('tradingplatformpoc.market.balance_manager.heat_trades_from_db_for_periods',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_heating_price(
                pd.DatetimeIndex([self.some_datetime]), heating_prices, None)
        self.assertEqual(1.5, [x.cost for x in extra_costs if x.agent == "Buyer1"][0])
        self.assertEqual(1.0, [x.cost for x in extra_costs if x.agent == "Buyer2"][0])

    def test_correct_for_exact_heating_price_external_buy(self):
        """
        Test basic functionality of correct_with_exact_heating_price when the external grid buys heating from the
        microgrid.
        The grid will be owed 10 * (0.5 - 0.25) = 2.50 SEK.
        Should be attributed 60% to seller 1, 40% to seller 2.
        """
        est_wholesale_price = 0.5
        exact_wholesale_price = 0.25
        trades = [
            Trade(Action.BUY, Resource.HEATING, 10, est_wholesale_price, "Grid", True, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.SELL, Resource.HEATING, 6, est_wholesale_price, "Seller1", False, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.SELL, Resource.HEATING, 4, est_wholesale_price, "Seller2", False, Market.LOCAL,
                  self.some_datetime)]

        heating_prices = pd.DataFrame.from_records([{
            'year': self.some_datetime.year,
            'month': self.some_datetime.month,
            'estimated_retail_price': np.nan,
            'estimated_wholesale_price': est_wholesale_price,
            'exact_retail_price': np.nan,
            'exact_wholesale_price': exact_wholesale_price}])
        
        with mock.patch('tradingplatformpoc.market.balance_manager.heat_trades_from_db_for_periods',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_heating_price(
                pd.DatetimeIndex([self.some_datetime]), heating_prices, None)
        self.assertEqual(1.5, [x.cost for x in extra_costs if x.agent == "Seller1"][0])
        self.assertEqual(1.0, [x.cost for x in extra_costs if x.agent == "Seller2"][0])

    def test_correct_for_exact_heating_price_external_sell_lower_price(self):
        """
        Test functionality of correct_with_exact_heating_price when the external grid sells heating to the microgrid,
        and the exact price turns out to be lower than the estimated price.
        The grid will be owed 10 * (0.25 - 0.5) = -2.50 SEK, i.e. grid the will owe the customer 2.50 SEK.
        Should be attributed 60% to buyer 1, 40% to buyer 2.
        """
        est_retail_price = 0.5
        exact_retail_price = 0.25
        trades = [
            Trade(Action.SELL, Resource.HEATING, 10, est_retail_price, "Grid", True, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 6, est_retail_price, "Buyer1", False, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 4, est_retail_price, "Buyer2", False, Market.LOCAL,
                  self.some_datetime)]

        heating_prices = pd.DataFrame.from_records([{
            'year': self.some_datetime.year,
            'month': self.some_datetime.month,
            'estimated_retail_price': est_retail_price,
            'estimated_wholesale_price': np.nan,
            'exact_retail_price': exact_retail_price,
            'exact_wholesale_price': np.nan}])
        
        with mock.patch('tradingplatformpoc.market.balance_manager.heat_trades_from_db_for_periods',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_heating_price(
                pd.DatetimeIndex([self.some_datetime]), heating_prices, None)
        self.assertEqual(-1.5, [x.cost for x in extra_costs if x.agent == "Buyer1"][0])
        self.assertEqual(-1.0, [x.cost for x in extra_costs if x.agent == "Buyer2"][0])

    def test_correct_for_exact_heating_price_with_local_producer(self):
        """
        Test basic functionality of correct_with_exact_heating_price, when there is a local producer of heating
        present, but there is a local deficit, and the exact retail price is bigger than the estimated retail price.
        The grid will be owed 1000 * (0.75 - 0.5) = 250 SEK.
        The local producer should not be affected.
        The debt should be attributed 75% to buyer 1, 25% to buyer 2.
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=34766880
        """
        est_retail_price = 0.5
        exact_retail_price = 0.75
        trades = [
            Trade(Action.SELL, Resource.HEATING, 1000, est_retail_price, "Grid", True, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 900, est_retail_price, "Buyer1", False, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 300, est_retail_price, "Buyer2", False, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.SELL, Resource.HEATING, 200, est_retail_price, "Seller", False, Market.LOCAL,
                  self.some_datetime)]

        heating_prices = pd.DataFrame.from_records([{
            'year': self.some_datetime.year,
            'month': self.some_datetime.month,
            'estimated_retail_price': est_retail_price,
            'estimated_wholesale_price': np.nan,
            'exact_retail_price': exact_retail_price,
            'exact_wholesale_price': np.nan}])
        
        # TODO: Here we use trades, but what is really returned is List[RowProxy]. Fix this?
        with mock.patch('tradingplatformpoc.market.balance_manager.heat_trades_from_db_for_periods',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_heating_price(
                pd.DatetimeIndex([self.some_datetime]), heating_prices, None)
        self.assertEqual(187.5, [x.cost for x in extra_costs if x.agent == "Buyer1"][0])
        self.assertEqual(62.5, [x.cost for x in extra_costs if x.agent == "Buyer2"][0])

    def test_calculate_heating_costs_two_steps(self):
        """
        Test both steps of heating balancing calculations: First, costs stemming from a discrepancy between estimated
        external price and exact external price. Second, costs stemming from bid inaccuracies
        which led to imports when there weren't expected to be any.
        """
        est_ws_price = 0.4
        est_retail_price = 0.5
        exact_ws_price = 0.6  # Irrelevant
        exact_retail_price = 0.75
        bids = [
            NetBidWithAcceptanceStatus(Action.SELL, Resource.HEATING, 200, est_retail_price, "Grid", True, 0),
            NetBidWithAcceptanceStatus(Action.BUY, Resource.HEATING, 6, math.inf, "Buyer1", False, 6),
            NetBidWithAcceptanceStatus(Action.BUY, Resource.HEATING, 4, math.inf, "Buyer2", False, 4),
            NetBidWithAcceptanceStatus(Action.SELL, Resource.HEATING, 11, 0, "Seller", False, 10)]
        # In market solver clearing price gets set to est_ws_price
        trades = [
            Trade(Action.SELL, Resource.HEATING, 3, est_retail_price, "Grid", True, Market.LOCAL, self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 6, est_ws_price, "Buyer1", False, Market.LOCAL, self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 6, est_ws_price, "Buyer2", False, Market.LOCAL, self.some_datetime),
            Trade(Action.SELL, Resource.HEATING, 9, est_ws_price, "Seller", False, Market.LOCAL, self.some_datetime)]

        # Buyer1 pays 6*0.4 = 2.4
        # Buyer2 pays 6*0.4 = 2.4
        # Grid receives 3*0.5 = 1.5 (estimated)
        # Seller receives 9*0.4 = 3.6
        # Total paid in 4.8, total paid out 5.1 estimated, discrepancy of 0.3.
        # Correcting for estimated - exact difference, grid is owed 3 * (0.75 - 0.5) = 0.75.
        # This cost is split proportionally between net consumers, Buyer1 and Buyer2.
        heating_prices = pd.DataFrame.from_records([{
            'year': self.some_datetime.year,
            'month': self.some_datetime.month,
            'estimated_retail_price': est_retail_price,
            'estimated_wholesale_price': est_ws_price,
            'exact_retail_price': exact_retail_price,
            'exact_wholesale_price': exact_ws_price}])
        
        # TODO: Here we use trades, but what is really returned is List[RowProxy]. Fix this?
        with mock.patch('tradingplatformpoc.market.balance_manager.heat_trades_from_db_for_periods',
                        return_value={self.some_datetime: trades}):
            cost_discr_corrs = correct_for_exact_heating_price(
                pd.DatetimeIndex([self.some_datetime]), heating_prices, None)
        self.assertAlmostEqual(0.375, [x.cost for x in cost_discr_corrs if x.agent == "Buyer1"][0], places=3)
        self.assertAlmostEqual(0.375, [x.cost for x in cost_discr_corrs if x.agent == "Buyer2"][0], places=3)
        self.assertAlmostEqual(-0.75, [x.cost for x in cost_discr_corrs if x.agent == "Grid"][0], places=3)

        # Step 2
        cost_to_be_paid_by_agent = calculate_penalty_costs_for_period_and_resource(bids,
                                                                                   trades,
                                                                                   est_ws_price,
                                                                                   est_ws_price)
        self.assertEqual(2, len(cost_to_be_paid_by_agent))
        self.assertAlmostEqual(0.2, cost_to_be_paid_by_agent["Buyer2"], places=3)
        self.assertAlmostEqual(0.1, cost_to_be_paid_by_agent["Seller"], places=3)

        # These two steps are independent of each other, so doesn't matter which one is done first

    def test_calculate_heating_costs_two_steps_external_sell(self):
        """
        Test both steps of heating balancing calculations: First, costs stemming from a discrepancy between estimated
        external price and exact external price. Second, costs stemming from bid
        inaccuracies which led to exports when there weren't expected to be any.
        """
        est_wholesale_price = 0.4
        est_retail_price = 0.5
        exact_wholesale_price = 0.42
        bids = [
            NetBidWithAcceptanceStatus(Action.SELL, Resource.HEATING, 200, est_retail_price, "Grid", True, 1),
            NetBidWithAcceptanceStatus(Action.BUY, Resource.HEATING, 6, math.inf, "Buyer1", False, 6),
            NetBidWithAcceptanceStatus(Action.BUY, Resource.HEATING, 4, math.inf, "Buyer2", False, 4),
            NetBidWithAcceptanceStatus(Action.SELL, Resource.HEATING, 9, 0, "Seller", False, 9)]
        # In market solver clearing price gets set to est_retail_price
        trades = [
            Trade(Action.BUY, Resource.HEATING, 1, est_wholesale_price, "Grid", True, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 6, est_retail_price, "Buyer1", False, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.BUY, Resource.HEATING, 2, est_retail_price, "Buyer2", False, Market.LOCAL,
                  self.some_datetime),
            Trade(Action.SELL, Resource.HEATING, 9, est_retail_price, "Seller", False, Market.LOCAL,
                  self.some_datetime)]

        # Buyer2 turned out to only need 2, so 1 had to get sold to grid, at a lower price
        # Buyer1 pays 6*0.5 = 3.0
        # Buyer2 pays 2*0.5 = 1.0
        # Grid pays 1*0.4 = 0.4
        # Seller receives 9*0.5 = 4.5
        # Total paid in 4.4 estimated, total paid out 4.5, discrepancy of 0.1.
        # In estimated - exact discrepancy calculation, Grid pays 1*(0.42-0.4) = 0.02 more, this is distributed among
        # sellers, but we have just one seller here, so +0.02 to "Seller" (i.e. a negative cost).
        # 0.02 - 0.02 = 0 so discrepancy is still 0.1.
        # Next, we look at bid inaccuracies. "Buyer2" was the only one who made an inaccurate bid, so she will take on
        # the full penalty of 0.1.
        heating_prices = pd.DataFrame.from_records([{
            'year': self.some_datetime.year,
            'month': self.some_datetime.month,
            'estimated_retail_price': est_retail_price,
            'estimated_wholesale_price': est_wholesale_price,
            'exact_retail_price': np.nan,
            'exact_wholesale_price': exact_wholesale_price}])

        # TODO: Here we use trades, but what is really returned is List[RowProxy]. Fix this?
        with mock.patch('tradingplatformpoc.market.balance_manager.heat_trades_from_db_for_periods',
                        return_value={self.some_datetime: trades}):
            cost_discr_corrs = correct_for_exact_heating_price(
                pd.DatetimeIndex([self.some_datetime]), heating_prices, None)
        self.assertAlmostEqual(0.02, [x.cost for x in cost_discr_corrs if x.agent == "Grid"][0], places=3)
        self.assertAlmostEqual(-0.02, [x.cost for x in cost_discr_corrs if x.agent == "Seller"][0], places=3)

        # Step 2
        cost_to_be_paid_by_agent = calculate_penalty_costs_for_period_and_resource(bids,
                                                                                   trades,
                                                                                   est_retail_price,
                                                                                   est_wholesale_price)
        self.assertEqual(1, len(cost_to_be_paid_by_agent))
        self.assertAlmostEqual(0.1, cost_to_be_paid_by_agent["Buyer2"], places=3)
