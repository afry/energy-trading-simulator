import unittest
import agent


class TestGridAgent(unittest.TestCase):

    gridAgent = agent.ElectricityGridAgent('../data/nordpool_area_grid_el_price.csv')

    def test_retail_price(self):
        self.assertEqual(self.gridAgent.calculate_retail_price("2019-01-01 00:00:00"), 0.58315)

    def test_wholesale_price(self):
        self.assertEqual(self.gridAgent.calculate_wholesale_price("2019-01-01 00:00:00"), 0.15315)


if __name__ == '__main__':
    unittest.main()
