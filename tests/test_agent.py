import unittest
import agent


class TestGridAgent(unittest.TestCase):

    gridAgent = agent.ElectricityGridAgent('../data/nordpool_area_grid_el_price.csv')

    def test_retail_price(self):
        self.assertEqual(self.gridAgent.calculate_retail_price("2019-01-01 00:00:00"), 0.58315)

    def test_wholesale_price(self):
        self.assertEqual(self.gridAgent.calculate_wholesale_price("2019-01-01 00:00:00"), 0.15315)

    def test_make_bids(self):
        bids = self.gridAgent.make_bids("2019-01-01 00:00:00")
        self.assertEqual(len(bids), 2)
        self.assertEqual(bids[0].resource, agent.Resource.ELECTRICITY)
        self.assertEqual(bids[1].resource, agent.Resource.ELECTRICITY)
        self.assertEqual(bids[0].action, agent.Action.SELL)
        self.assertEqual(bids[1].action, agent.Action.BUY)
        self.assertTrue(bids[0].quantity > 0)
        self.assertTrue(bids[1].quantity > 0)
        self.assertTrue(bids[0].price > bids[1].price)


if __name__ == '__main__':
    unittest.main()
