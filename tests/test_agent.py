import unittest
from unittest import TestCase

import agent
import bid
import data_store

data_store_entity = data_store.DataStore('../data/nordpool_area_grid_el_price.csv',
                                         '../data/full_mock_energy_data.csv')


class TestGridAgent(unittest.TestCase):
    grid_agent = agent.ElectricityGridAgent(data_store_entity)

    def test_retail_price(self):
        self.assertEqual(0.99871, self.grid_agent.calculate_retail_price("2019-02-01 01:00:00"))

    def test_wholesale_price(self):
        self.assertEqual(0.56871, self.grid_agent.calculate_wholesale_price("2019-02-01 01:00:00"))

    def test_make_bids(self):
        bids = self.grid_agent.make_bids("2019-02-01 01:00:00")
        self.assertEqual(2, len(bids))
        self.assertEqual(bid.Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(bid.Resource.ELECTRICITY, bids[1].resource)
        self.assertEqual(bid.Action.SELL, bids[0].action)
        self.assertEqual(bid.Action.BUY, bids[1].action)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[1].quantity > 0)
        self.assertTrue(bids[0].price > bids[1].price)


class TestBatteryStorageAgent(unittest.TestCase):
    battery_agent = agent.BatteryStorageAgent(1000)

    def test_make_bids(self):
        bids = self.battery_agent.make_bids("")
        self.assertEqual(bids[0].resource, bid.Resource.ELECTRICITY)
        self.assertEqual(bids[0].action, bid.Action.BUY)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].quantity <= 1000)
        self.assertTrue(bids[0].price > 0)


if __name__ == '__main__':
    unittest.main()


class TestBuildingAgent(TestCase):
    building_agent = agent.BuildingAgent(data_store_entity)

    def test_make_bids(self):
        bids = self.building_agent.make_bids("2019-02-01 01:00:00")
        self.assertEqual(bids[0].resource, bid.Resource.ELECTRICITY)
        self.assertEqual(bids[0].action, bid.Action.BUY)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[0].price > 0)
