import datetime
from unittest import TestCase, mock

import numpy as np

import pandas as pd

import pytz

from tradingplatformpoc.market.balance_manager import correct_for_exact_price_for_lec, \
    correct_for_exact_price_no_lec
from tradingplatformpoc.market.extra_cost import ExtraCostType
from tradingplatformpoc.market.trade import Action, Market, Resource, Trade


class TestBalanceManager(TestCase):
    some_datetime = datetime.datetime(2019, 1, 2, tzinfo=pytz.utc)

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
            Trade(self.some_datetime, Action.SELL, Resource.HIGH_TEMP_HEAT, 10, est_retail_price, "Grid", True,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 6, est_retail_price, "Buyer1", False,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 4, est_retail_price, "Buyer2", False,
                  Market.LOCAL)]

        heating_prices = pd.DataFrame.from_records([{
            'period': self.some_datetime,
            'estimated_retail_price': est_retail_price,
            'estimated_wholesale_price': np.nan,
            'exact_retail_price': exact_retail_price,
            'exact_wholesale_price': np.nan}])

        with mock.patch('tradingplatformpoc.market.balance_manager.all_trades_for_resource_from_db',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_price_for_lec(pd.DatetimeIndex([self.some_datetime]), heating_prices,
                                                          Resource.HIGH_TEMP_HEAT, ExtraCostType.HEAT_EXT_COST_CORR,
                                                          "job_id")
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
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 10, est_wholesale_price, "Grid", True,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.SELL, Resource.HIGH_TEMP_HEAT, 6, est_wholesale_price, "Seller1", False,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.SELL, Resource.HIGH_TEMP_HEAT, 4, est_wholesale_price, "Seller2", False,
                  Market.LOCAL)]

        heating_prices = pd.DataFrame.from_records([{
            'period': self.some_datetime,
            'estimated_retail_price': np.nan,
            'estimated_wholesale_price': est_wholesale_price,
            'exact_retail_price': np.nan,
            'exact_wholesale_price': exact_wholesale_price}])
        
        with mock.patch('tradingplatformpoc.market.balance_manager.all_trades_for_resource_from_db',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_price_for_lec(pd.DatetimeIndex([self.some_datetime]), heating_prices,
                                                          Resource.HIGH_TEMP_HEAT, ExtraCostType.HEAT_EXT_COST_CORR,
                                                          "job_id")
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
            Trade(self.some_datetime, Action.SELL, Resource.HIGH_TEMP_HEAT, 10, est_retail_price, "Grid", True,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 6, est_retail_price, "Buyer1", False,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 4, est_retail_price, "Buyer2", False,
                  Market.LOCAL)]

        heating_prices = pd.DataFrame.from_records([{
            'period': self.some_datetime,
            'estimated_retail_price': est_retail_price,
            'estimated_wholesale_price': np.nan,
            'exact_retail_price': exact_retail_price,
            'exact_wholesale_price': np.nan}])
        
        with mock.patch('tradingplatformpoc.market.balance_manager.all_trades_for_resource_from_db',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_price_for_lec(pd.DatetimeIndex([self.some_datetime]), heating_prices,
                                                          Resource.HIGH_TEMP_HEAT, ExtraCostType.HEAT_EXT_COST_CORR,
                                                          "job_id")
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
            Trade(self.some_datetime, Action.SELL, Resource.HIGH_TEMP_HEAT, 1000, est_retail_price, "Grid", True,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 900, est_retail_price, "Buyer1", False,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 300, est_retail_price, "Buyer2", False,
                  Market.LOCAL),
            Trade(self.some_datetime, Action.SELL, Resource.HIGH_TEMP_HEAT, 200, est_retail_price, "Seller", False,
                  Market.LOCAL)]

        heating_prices = pd.DataFrame.from_records([{
            'period': self.some_datetime,
            'estimated_retail_price': est_retail_price,
            'estimated_wholesale_price': np.nan,
            'exact_retail_price': exact_retail_price,
            'exact_wholesale_price': np.nan}])

        with mock.patch('tradingplatformpoc.market.balance_manager.all_trades_for_resource_from_db',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_price_for_lec(pd.DatetimeIndex([self.some_datetime]), heating_prices,
                                                          Resource.HIGH_TEMP_HEAT, ExtraCostType.HEAT_EXT_COST_CORR,
                                                          "job_id")
        self.assertEqual(187.5, [x.cost for x in extra_costs if x.agent == "Buyer1"][0])
        self.assertEqual(62.5, [x.cost for x in extra_costs if x.agent == "Buyer2"][0])

    def test_no_lec(self):
        """
        Test basic functionality of correct_with_exact_heating_price when there is no Local Energy Community, so the
        agents should be considered individually.
        The grid will be owed 4 * (0.75 - 0.5) = 1.00 SEK from Buyer2, and 0 from Buyer1 since the estimated price was
        equal to the exact.
        """
        est_retail_price = 0.5
        exact_retail_price_1 = 0.5
        exact_retail_price_2 = 0.75
        trades = [
            Trade(self.some_datetime, Action.SELL, Resource.HIGH_TEMP_HEAT, 6, est_retail_price, "Grid", True,
                  Market.EXTERNAL),
            Trade(self.some_datetime, Action.SELL, Resource.HIGH_TEMP_HEAT, 4, est_retail_price, "Grid", True,
                  Market.EXTERNAL),
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 6, est_retail_price, "Buyer1", False,
                  Market.EXTERNAL),
            Trade(self.some_datetime, Action.BUY, Resource.HIGH_TEMP_HEAT, 4, est_retail_price, "Buyer2", False,
                  Market.EXTERNAL)]

        heating_prices = pd.DataFrame.from_records([
            {
                'period': self.some_datetime,
                'agent': "Buyer1",
                'estimated_retail_price': est_retail_price,
                'estimated_wholesale_price': np.nan,
                'exact_retail_price': exact_retail_price_1,
                'exact_wholesale_price': np.nan
            }, {
                'period': self.some_datetime,
                'agent': "Buyer2",
                'estimated_retail_price': est_retail_price,
                'estimated_wholesale_price': np.nan,
                'exact_retail_price': exact_retail_price_2,
                'exact_wholesale_price': np.nan
            }
        ])

        with mock.patch('tradingplatformpoc.market.balance_manager.all_trades_for_resource_from_db',
                        return_value={self.some_datetime: trades}):
            extra_costs = correct_for_exact_price_no_lec(
                pd.DatetimeIndex([self.some_datetime]), heating_prices,
                Resource.HIGH_TEMP_HEAT, ExtraCostType.HEAT_EXT_COST_CORR,
                "job_id", ["Buyer1", "Buyer2"])
        self.assertEqual(0.0, [x.cost for x in extra_costs if x.agent == "Buyer1"][0])
        self.assertEqual(1.0, [x.cost for x in extra_costs if x.agent == "Buyer2"][0])
