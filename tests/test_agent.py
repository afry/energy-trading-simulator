import unittest
from datetime import datetime
from unittest import TestCase

import numpy as np

import pandas as pd

import tradingplatformpoc.agent.building_agent
import tradingplatformpoc.agent.grid_agent
import tradingplatformpoc.agent.grocery_store_agent
import tradingplatformpoc.agent.pv_agent
import tradingplatformpoc.agent.storage_agent
from tradingplatformpoc import agent, data_store
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.trade import Market, Trade
from tradingplatformpoc.trading_platform_utils import datetime_array_between

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

    grid_agent = tradingplatformpoc.agent.grid_agent.ElectricityGridAgent(data_store_entity)

    def test_make_bids(self):
        """Test basic functionality of GridAgent's make_bids method."""
        bids = self.grid_agent.make_bids(datetime(2019, 2, 1, 1, 0, 0))
        self.assertEqual(1, len(bids))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)

    def test_calculate_trades_1(self):
        """Test basic functionality of GridAgent's calculate_external_trades method when there is a local deficit."""
        retail_price = 3.938725389630498
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BuildingAgent", False, Market.LOCAL,
                  datetime(2019, 2, 1, 1))
        ]
        external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, retail_price)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.SELL, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(trades_excl_external[0].quantity, external_trades[0].quantity)
        self.assertAlmostEqual(retail_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(datetime(2019, 2, 1, 1, 0, 0), external_trades[0].period)

    def test_calculate_trades_local_equilibrium(self):
        """Test the calculate_external_trades method when there is no need for any external trades."""
        retail_price = 0.99871
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BuildingAgent", False, Market.LOCAL,
                  datetime(2019, 2, 1, 1, 0, 0)),
            Trade(Action.SELL, Resource.ELECTRICITY, 100, retail_price, "PVAgent", False, Market.LOCAL,
                  datetime(2019, 2, 1, 1, 0, 0))
        ]
        external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, retail_price)
        self.assertEqual(0, len(external_trades))

    def test_calculate_trades_price_not_matching(self):
        """Test that an error is raised when the local price is specified as greater than the external retail price."""
        local_price = MAX_NORDPOOL_PRICE + 1.0
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, local_price, "BuildingAgent", False, Market.LOCAL,
                  datetime(2019, 2, 1, 1, 0, 0))
        ]
        with self.assertRaises(RuntimeError):
            external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, local_price)

    def test_calculate_trades_price_not_matching_2(self):
        """Test calculate_external_trades when local price is lower than the retail price, but there is a need for
        importing of energy. This will lead to penalisation of someone, but shouldn't raise an error."""
        local_price = MIN_NORDPOOL_PRICE - 1.0
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, local_price, "BuildingAgent", False, Market.LOCAL,
                  datetime(2019, 2, 1, 1, 0, 0))
        ]
        # Should log a line about external grid and market clearing price being different
        external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, local_price)
        self.assertEqual(1, len(external_trades))

    def test_calculate_trades_2(self):
        """Test basic functionality of GridAgent's calculate_external_trades method when there is a local surplus."""
        wholesale_price = 3.5087253896304977
        period = datetime(2019, 2, 1, 1, 0, 0)
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, wholesale_price, "BuildingAgent", False, Market.LOCAL, period),
            Trade(Action.BUY, Resource.ELECTRICITY, 200, wholesale_price, "GSAgent", False, Market.LOCAL, period),
            Trade(Action.SELL, Resource.ELECTRICITY, 400, wholesale_price, "PvAgent", False, Market.LOCAL, period)
        ]
        external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, wholesale_price)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.BUY, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(100, external_trades[0].quantity)
        self.assertAlmostEqual(wholesale_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(period, external_trades[0].period)


class TestStorageAgent(unittest.TestCase):
    twin = StorageDigitalTwin(max_capacity_kwh=1000, max_charge_rate_fraction=0.1, max_discharge_rate_fraction=0.1)
    battery_agent = tradingplatformpoc.agent.storage_agent.StorageAgent(data_store_entity, twin, 168, 20, 80)

    def test_make_bids(self):
        """Test basic functionality of StorageAgent's make_bids method."""
        bids = self.battery_agent.make_bids(datetime(2019, 2, 1, 1, 0, 0), {})
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.BUY, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].quantity <= 1000)
        self.assertTrue(bids[0].price > 0)


class TestBuildingAgent(TestCase):
    # Won't test exact values so don't need to set random seed
    elec_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    heat_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    building_digital_twin = StaticDigitalTwin(electricity_usage=pd.Series(elec_values, index=DATETIME_ARRAY),
                                              heating_usage=pd.Series(heat_values, index=DATETIME_ARRAY))
    building_agent = agent.building_agent.BuildingAgent(data_store_entity, building_digital_twin)

    def test_make_bids(self):
        """Test basic functionality of BuildingAgent's make_bids method."""
        bids = self.building_agent.make_bids(datetime(2019, 2, 1, 1, 0, 0))
        self.assertEqual(bids[0].resource, Resource.ELECTRICITY)
        self.assertEqual(bids[0].action, Action.BUY)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].price > 0)


class TestGroceryStoreAgent(TestCase):
    # Won't test exact values so don't need to set random seed
    elec_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    heat_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=pd.Series(elec_values, index=DATETIME_ARRAY),
                                                   heating_usage=pd.Series(heat_values, index=DATETIME_ARRAY),
                                                   electricity_production=data_store_entity.coop_pv_prod)
    grocery_store_agent = tradingplatformpoc.agent.grocery_store_agent.GroceryStoreAgent(data_store_entity,
                                                                                         grocery_store_digital_twin)

    def test_make_bids(self):
        """Test basic functionality of GroceryStoreAgent's make_bids method."""
        bids = self.grocery_store_agent.make_bids(datetime(2019, 7, 7, 11, 0, 0))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.BUY, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].price > 1000)


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
