import unittest
from datetime import datetime
from unittest import TestCase

import numpy as np

import pandas as pd

import tradingplatformpoc.agent.building_agent
import tradingplatformpoc.agent.grid_agent
import tradingplatformpoc.agent.pv_agent
import tradingplatformpoc.agent.storage_agent
from tradingplatformpoc import agent, data_store
from tradingplatformpoc.bid import Action, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.trade import Market, Trade
from tradingplatformpoc.trading_platform_utils import datetime_array_between

SOME_DATETIME = datetime(2019, 2, 1, 1)

MAX_NORDPOOL_PRICE = 4.0

MIN_NORDPOOL_PRICE = 0.1

AREA_INFO = {
    "ParkPVArea": 24324.3,
    "StorePVArea": 320,
    "PVEfficiency": 0.165
}
DATETIME_ARRAY = datetime_array_between(datetime(2018, 12, 31, 23), datetime(2020, 1, 31, 22))

# To make tests consistent, set a random seed
np.random.seed(1)
# Create data
nordpool_values = np.random.uniform(MIN_NORDPOOL_PRICE, MAX_NORDPOOL_PRICE, len(DATETIME_ARRAY))
irradiation_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
#
data_store_entity = data_store.DataStore(config_area_info=AREA_INFO,
                                         nordpool_data=pd.Series(nordpool_values, index=DATETIME_ARRAY),
                                         irradiation_data=pd.Series(irradiation_values, index=DATETIME_ARRAY))


class TestGridAgent(unittest.TestCase):
    electricity_grid_agent = tradingplatformpoc.agent.grid_agent.GridAgent(data_store_entity, Resource.ELECTRICITY,
                                                                           guid='ElectricityGridAgent')
    heating_grid_agent = tradingplatformpoc.agent.grid_agent.GridAgent(data_store_entity, Resource.HEATING,
                                                                       guid='HeatingGridAgent')

    def test_make_bids_electricity(self):
        """Test basic functionality of GridAgent's make_bids method, for the ELECTRICITY resource."""
        bids = self.electricity_grid_agent.make_bids(SOME_DATETIME)
        self.assertEqual(1, len(bids))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)

    def test_make_bids_heating(self):
        """Test basic functionality of GridAgent's make_bids method, for the HEATING resource."""
        bids = self.heating_grid_agent.make_bids(SOME_DATETIME)
        self.assertEqual(1, len(bids))
        self.assertEqual(Resource.HEATING, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)

    def test_calculate_trades_1(self):
        """Test basic functionality of GridAgent's calculate_external_trades method when there is a local deficit."""
        retail_price = 3.938725389630498
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BuildingAgent", False, Market.LOCAL,
                  SOME_DATETIME)
        ]
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, retail_price)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.SELL, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(trades_excl_external[0].quantity, external_trades[0].quantity)
        self.assertAlmostEqual(retail_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(SOME_DATETIME, external_trades[0].period)

    def test_calculate_trades_local_equilibrium(self):
        """Test the calculate_external_trades method when there is no need for any external trades."""
        retail_price = 0.99871
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BuildingAgent", False, Market.LOCAL,
                  SOME_DATETIME),
            Trade(Action.SELL, Resource.ELECTRICITY, 100, retail_price, "PVAgent", False, Market.LOCAL,
                  SOME_DATETIME)
        ]
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, retail_price)
        self.assertEqual(0, len(external_trades))

    def test_calculate_trades_price_not_matching(self):
        """Test that a warning is logged when the local price is specified as greater than the external retail price."""
        local_price = MAX_NORDPOOL_PRICE + 1.0
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, local_price, "BuildingAgent", False, Market.LOCAL,
                  SOME_DATETIME)
        ]
        with self.assertLogs() as captured:
            self.electricity_grid_agent.calculate_external_trades(trades_excl_external, local_price)
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(captured.records[0].levelname, 'WARNING')

    def test_calculate_trades_price_not_matching_2(self):
        """Test calculate_external_trades when local price is lower than the retail price, but there is a need for
        importing of energy. This will lead to penalisation of someone, but shouldn't raise an error."""
        local_price = MIN_NORDPOOL_PRICE - 1.0
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, local_price, "BuildingAgent", False, Market.LOCAL,
                  SOME_DATETIME)
        ]
        # Should log a line about external grid and market clearing price being different
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, local_price)
        self.assertEqual(1, len(external_trades))

    def test_calculate_trades_2(self):
        """Test basic functionality of GridAgent's calculate_external_trades method when there is a local surplus."""
        wholesale_price = 3.5087253896304977
        period = SOME_DATETIME
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, wholesale_price, "BuildingAgent", False, Market.LOCAL, period),
            Trade(Action.BUY, Resource.ELECTRICITY, 200, wholesale_price, "GSAgent", False, Market.LOCAL, period),
            Trade(Action.SELL, Resource.ELECTRICITY, 400, wholesale_price, "PvAgent", False, Market.LOCAL, period)
        ]
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, wholesale_price)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.BUY, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(100, external_trades[0].quantity)
        self.assertAlmostEqual(wholesale_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(period, external_trades[0].period)

    def test_calculate_trades_with_some_bids_with_other_resource(self):
        """When sent into an electricity grid agent, heating trades should be ignored."""
        retail_price = 3.938725389630498
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BuildingAgent", False, Market.LOCAL,
                  SOME_DATETIME),
            Trade(Action.BUY, Resource.HEATING, 100, retail_price, "BuildingAgent", False, Market.LOCAL,
                  SOME_DATETIME)
        ]
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, retail_price)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.SELL, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(trades_excl_external[0].quantity, external_trades[0].quantity)
        self.assertAlmostEqual(retail_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(SOME_DATETIME, external_trades[0].period)


class TestStorageAgent(unittest.TestCase):
    twin = StorageDigitalTwin(max_capacity_kwh=1000, max_charge_rate_fraction=0.1, max_discharge_rate_fraction=0.1,
                              discharging_efficiency=0.93)
    battery_agent = tradingplatformpoc.agent.storage_agent.StorageAgent(data_store_entity, twin, 168, 20, 80)

    def test_make_bids(self):
        """Test basic functionality of StorageAgent's make_bids method."""
        bids = self.battery_agent.make_bids(SOME_DATETIME, {})
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.BUY, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].quantity <= 1000)
        self.assertTrue(bids[0].price > 0)

    def test_make_bids_without_historical_prices(self):
        """Test that a warning is logged when calling StorageAgent's make_bids with None clearing_prices_dict"""
        with self.assertLogs() as captured:
            self.battery_agent.make_bids(SOME_DATETIME, None)
        self.assertTrue(len(captured.records) > 0)
        log_levels_captured = [rec.levelname for rec in captured.records]
        self.assertTrue('WARNING' in log_levels_captured)

    def test_make_bids_without_historical_prices_or_nordpool_prices(self):
        """Test that an error is raised when calling StorageAgent's make_bids for a time period when there is no price
        data available whatsoever, local nor Nordpool"""
        with self.assertRaises(RuntimeError):
            self.battery_agent.make_bids(datetime(1990, 1, 1), {})

    def test_make_bids_without_historical_prices_and_only_1_day_of_nordpool_prices(self):
        """Test that an error is raised when calling StorageAgent's make_bids for a time period when there is only
        one day's worth of entries of Nordpool data available."""
        early_datetime = data_store_entity.get_nordpool_data_datetimes()[24]
        with self.assertRaises(RuntimeError):
            self.battery_agent.make_bids(early_datetime, {})

    def test_make_bids_without_historical_prices_and_only_5_days_of_nordpool_prices(self):
        """Test that an INFO is logged when calling StorageAgent's make_bids for a time period when there are only
        five day's worth of entries of Nordpool data available."""
        quite_early_datetime = data_store_entity.get_nordpool_data_datetimes()[120]
        with self.assertLogs() as captured:
            self.battery_agent.make_bids(quite_early_datetime, {})
        self.assertTrue(len(captured.records) > 0)
        log_levels_captured = [rec.levelname for rec in captured.records]
        self.assertTrue('INFO' in log_levels_captured)

    def test_make_trade_with_2_accepted_bids(self):
        """Test that an error is raised when trying to calculate what trade to make, with more than 1 accepted bid."""
        accepted_bids_for_agent = [
            BidWithAcceptanceStatus(Action.BUY, Resource.ELECTRICITY, 100, 1, 'StorageAgent', False, True),
            BidWithAcceptanceStatus(Action.SELL, Resource.ELECTRICITY, 100, 1, 'StorageAgent', False, True)
        ]
        with self.assertRaises(RuntimeError):
            self.battery_agent.make_trade_given_clearing_price(SOME_DATETIME, 1.0, {}, accepted_bids_for_agent)


class TestBuildingAgent(TestCase):
    # Won't test exact values so don't need to set random seed
    elec_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    heat_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    building_digital_twin_cons = StaticDigitalTwin(electricity_usage=pd.Series(elec_values, index=DATETIME_ARRAY),
                                                   heating_usage=pd.Series(heat_values, index=DATETIME_ARRAY))
    building_agent_cons = agent.building_agent.BuildingAgent(data_store_entity, building_digital_twin_cons)
    building_digital_twin_prod = StaticDigitalTwin(electricity_usage=-pd.Series(elec_values, index=DATETIME_ARRAY),
                                                   heating_usage=-pd.Series(heat_values, index=DATETIME_ARRAY))
    building_agent_prod = agent.building_agent.BuildingAgent(data_store_entity, building_digital_twin_prod)

    def test_make_bids_consumer(self):
        """Test basic functionality of BuildingAgent's make_bids method."""
        bids = self.building_agent_cons.make_bids(SOME_DATETIME)
        self.assertEqual(bids[0].resource, Resource.ELECTRICITY)
        self.assertEqual(bids[0].action, Action.BUY)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].price > 0)

    def test_make_bids_producer(self):
        """Test basic functionality of BuildingAgent's make_bids method."""
        bids = self.building_agent_prod.make_bids(SOME_DATETIME)
        self.assertEqual(bids[0].resource, Resource.ELECTRICITY)
        self.assertEqual(bids[0].action, Action.SELL)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].price > 0)

    def test_make_prognosis(self):
        """Test basic functionality of BuildingAgent's make_prognosis method."""
        prognosis_consumer = self.building_agent_cons.make_prognosis(SOME_DATETIME)
        self.assertFalse(np.isnan(prognosis_consumer))
        self.assertTrue(prognosis_consumer > 0)
        prognosis_producer = self.building_agent_prod.make_prognosis(SOME_DATETIME)
        self.assertFalse(np.isnan(prognosis_producer))
        self.assertTrue(prognosis_producer < 0)

    def test_make_prognosis_for_first_data_point(self):
        """BuildingAgent's make_prognosis method currently just looks up the previous actual value, so here we test
        what happens when we try to make a prognosis for the first value."""
        prognosis_consumer = self.building_agent_cons.make_prognosis(DATETIME_ARRAY[0])
        self.assertFalse(np.isnan(prognosis_consumer))
        self.assertTrue(prognosis_consumer > 0)
        prognosis_producer = self.building_agent_prod.make_prognosis(DATETIME_ARRAY[0])
        self.assertFalse(np.isnan(prognosis_producer))
        self.assertTrue(prognosis_producer < 0)

    def test_get_actual_usage(self):
        """Test basic functionality of BuildingAgent's get_actual_usage method."""
        usage_consumer = self.building_agent_cons.get_actual_usage(SOME_DATETIME)
        self.assertFalse(np.isnan(usage_consumer))
        self.assertTrue(usage_consumer > 0)
        usage_producer = self.building_agent_prod.get_actual_usage(SOME_DATETIME)
        self.assertFalse(np.isnan(usage_producer))
        self.assertTrue(usage_producer < 0)

    def test_make_trade_given_clearing_price_consumer(self):
        """Test basic functionality of BuildingAgent's make_trade_given_clearing_price method."""
        trade = self.building_agent_cons.make_trade_given_clearing_price(SOME_DATETIME, 0.01, {}, [])
        self.assertEqual(trade.resource, Resource.ELECTRICITY)
        self.assertEqual(trade.action, Action.BUY)
        self.assertTrue(trade.quantity > 0)
        self.assertTrue(trade.price > 0)
        self.assertEqual(trade.source, self.building_agent_cons.guid)
        self.assertFalse(trade.by_external)
        self.assertEqual(trade.market, Market.LOCAL)
        self.assertEqual(trade.period, SOME_DATETIME)

    def test_make_trade_given_low_clearing_price_producer(self):
        """Test basic functionality of BuildingAgent's make_trade_given_clearing_price method."""
        trade = self.building_agent_prod.make_trade_given_clearing_price(SOME_DATETIME, 0.01, {}, [])
        self.assertEqual(trade.resource, Resource.ELECTRICITY)
        self.assertEqual(trade.action, Action.SELL)
        self.assertTrue(trade.quantity > 0)
        self.assertTrue(trade.price >= MIN_NORDPOOL_PRICE)
        self.assertEqual(trade.source, self.building_agent_prod.guid)
        self.assertFalse(trade.by_external)
        self.assertEqual(trade.market, Market.EXTERNAL)  # Very low local price, so should sell to external
        self.assertEqual(trade.period, SOME_DATETIME)

    def test_make_trade_given_high_clearing_price_producer(self):
        """Test basic functionality of BuildingAgent's make_trade_given_clearing_price method."""
        local_clearing_price = 100.0
        trade = self.building_agent_prod.make_trade_given_clearing_price(SOME_DATETIME, local_clearing_price, {}, [])
        self.assertEqual(trade.resource, Resource.ELECTRICITY)
        self.assertEqual(trade.action, Action.SELL)
        self.assertTrue(trade.quantity > 0)
        self.assertAlmostEqual(trade.price, local_clearing_price)
        self.assertEqual(trade.source, self.building_agent_prod.guid)
        self.assertFalse(trade.by_external)
        self.assertEqual(trade.market, Market.LOCAL)  # Very low local price, so should sell to external
        self.assertEqual(trade.period, SOME_DATETIME)


class TestPVAgent(TestCase):
    pv_digital_twin = StaticDigitalTwin(electricity_production=data_store_entity.tornet_park_pv_prod)
    tornet_pv_agent = tradingplatformpoc.agent.pv_agent.PVAgent(data_store_entity, pv_digital_twin)

    def test_make_bids(self):
        """Test basic functionality of PVAgent's make_bids method."""
        bids = self.tornet_pv_agent.make_bids(datetime(2019, 7, 7, 11, 0, 0))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertAlmostEqual(325.1019614111333, bids[0].quantity)
        self.assertAlmostEqual(2.8295860496253016, bids[0].price)
