import unittest
from unittest import TestCase

import agent
import data_store
from trade import Trade, Market
from bid import Action, Resource

data_store_entity = data_store.DataStore('../data/nordpool_area_grid_el_price.csv',
                                         '../data/full_mock_energy_data.csv')


class TestGridAgent(unittest.TestCase):
    grid_agent = agent.ElectricityGridAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.grid_agent.make_bids("2019-02-01 01:00:00")
        self.assertEqual(2, len(bids))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Resource.ELECTRICITY, bids[1].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertEqual(Action.BUY, bids[1].action)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[1].quantity > 0)
        self.assertTrue(bids[0].price > bids[1].price)

    def test_calculate_trades_1(self):
        trades_excl_external = [
            Trade(Action.BUY, Resource.ELECTRICITY, 100, 0.99871, "BuildingAgent", Market.LOCAL, "2019-02-01 01:00:00")
        ]
        external_trades = self.grid_agent.calculate_external_trades(trades_excl_external, 0.99871)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.SELL, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(trades_excl_external[0].quantity, external_trades[0].quantity)
        self.assertEqual(trades_excl_external[0].price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual("2019-02-01 01:00:00", external_trades[0].period)


class TestBatteryStorageAgent(unittest.TestCase):
    battery_agent = agent.BatteryStorageAgent(1000)

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
    building_agent = agent.BuildingAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.building_agent.make_bids("2019-02-01 01:00:00")
        self.assertEqual(bids[0].resource, Resource.ELECTRICITY)
        self.assertEqual(bids[0].action, Action.BUY)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].price > 0)


class TestGroceryStoreAgent(TestCase):
    grocery_store_agent = agent.GroceryStoreAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.grocery_store_agent.make_bids("2019-07-07 11:00:00")
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.BUY, bids[0].action)
        self.assertEqual(bids[0].quantity, 190.95254204748102)
        self.assertTrue(bids[0].price > 1000)


class TestPVAgent(TestCase):
    tornet_pv_agent = agent.PVAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.tornet_pv_agent.make_bids("2019-07-07 11:00:00")
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertEqual(271.5033816, bids[0].quantity)
        self.assertEqual(0.34389, bids[0].price)
