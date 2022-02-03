import datetime
from unittest import TestCase

from tradingplatformpoc.district_heating_calculations import estimate_district_heating_price


class Test(TestCase):
    # Rough prices:
    # Jan - Feb: 0.55 + 0.66 + 0.10 = 1.31 SEK / kWh
    # Mar - Apr: 0.55 + 0.10 = 0.65 SEK / kWh
    # May - Sep: 0.35 + 0.10 = 0.45 SEK / kWh
    # Oct - Dec: 0.55 + 0.10 = 0.65 SEK / kWh

    def test_estimate_district_heating_price_jan(self):
        self.assertAlmostEqual(1.311891744, estimate_district_heating_price(datetime.datetime(2019, 1, 1)))

    def test_estimate_district_heating_price_feb(self):
        self.assertAlmostEqual(1.322548426, estimate_district_heating_price(datetime.datetime(2019, 2, 1)))

    def test_estimate_district_heating_price_mar(self):
        self.assertAlmostEqual(0.649462366, estimate_district_heating_price(datetime.datetime(2019, 3, 1)))

    def test_estimate_district_heating_price_may(self):
        self.assertAlmostEqual(0.429462366, estimate_district_heating_price(datetime.datetime(2019, 5, 1)))
