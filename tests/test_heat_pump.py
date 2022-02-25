from unittest import TestCase

from tradingplatformpoc import heat_pump

class Test(TestCase):

    def test_something_or_other(self):
        test_pump = heat_pump.HeatPump
        # What are good test parameters?
        test_things = test_pump.get_heatpump_throughputs()