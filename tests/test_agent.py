import unittest
import json
from datetime import datetime
from unittest import TestCase

from tradingplatformpoc import data_store, agent
from tradingplatformpoc.bid import Resource, Action
from tradingplatformpoc.trade import Trade, Market

import tradingplatformpoc.agent.building_agent
import tradingplatformpoc.agent.grid_agent
import tradingplatformpoc.agent.grocery_store_agent
import tradingplatformpoc.agent.pv_agent
import tradingplatformpoc.agent.storage_agent

with open("../data/jonstaka.json", "r") as jsonfile:
    config_data = json.load(jsonfile)
data_store_entity = data_store.DataStore(config_data=config_data["AreaInfo"])


class TestGridAgent(unittest.TestCase):
    grid_agent = tradingplatformpoc.agent.grid_agent.ElectricityGridAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.grid_agent.make_bids(datetime(2019, 2, 1, 1, 0, 0))
        self.assertEqual(1, len(bids))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)

    def test_calculate_trades_1(self):
        retail_price = 0.99871
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BuildingAgent", False, Market.LOCAL,
                  datetime(2019, 2, 1, 1, 0, 0))
        ]
        external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, retail_price)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.SELL, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(trades_excl_external[0].quantity, external_trades[0].quantity)
        self.assertEqual(retail_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(datetime(2019, 2, 1, 1, 0, 0), external_trades[0].period)

    def test_calculate_trades_local_equilibrium(self):
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
        local_price = 1
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, local_price, "BuildingAgent", False, Market.LOCAL,
                  datetime(2019, 2, 1, 1, 0, 0))
        ]
        with self.assertRaises(RuntimeError):
            external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, local_price)

    def test_calculate_trades_price_not_matching_2(self):
        local_price = 0.5
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, local_price, "BuildingAgent", False, Market.LOCAL,
                  datetime(2019, 2, 1, 1, 0, 0))
        ]
        # Should log a line about external grid and market clearing price being different
        external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, local_price)
        self.assertEqual(1, len(external_trades))

    def test_calculate_trades_2(self):
        wholesale_price = 0.56871
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
        self.assertEqual(wholesale_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(period, external_trades[0].period)


class TestBatteryStorageAgent(unittest.TestCase):
    battery_agent = tradingplatformpoc.agent.storage_agent.BatteryStorageAgent(data_store_entity, max_capacity=1000)

    def test_make_bids(self):
        bids = self.battery_agent.make_bids("")
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.BUY, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].quantity <= 1000)
        self.assertTrue(bids[0].price > 0)


if __name__ == '__main__':
    unittest.main()


class TestBuildingAgent(TestCase):
    building_agent = agent.building_agent.BuildingAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.building_agent.make_bids(datetime(2019, 2, 1, 1, 0, 0))
        self.assertEqual(bids[0].resource, Resource.ELECTRICITY)
        self.assertEqual(bids[0].action, Action.BUY)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].price > 0)


class TestGroceryStoreAgent(TestCase):
    grocery_store_agent = tradingplatformpoc.agent.grocery_store_agent.GroceryStoreAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.grocery_store_agent.make_bids(datetime(2019, 7, 7, 11, 0, 0))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.BUY, bids[0].action)
        self.assertEqual(193.76252792024837, bids[0].quantity)
        self.assertTrue(bids[0].price > 1000)


class TestPVAgent(TestCase):
    tornet_pv_agent = tradingplatformpoc.agent.pv_agent.PVAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.tornet_pv_agent.make_bids(datetime(2019, 7, 7, 11, 0, 0))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertEqual(6443.1607812, bids[0].quantity)
        self.assertEqual(0.34389, bids[0].price)
