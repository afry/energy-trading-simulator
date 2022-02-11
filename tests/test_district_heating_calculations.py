import datetime
from unittest import TestCase

import numpy as np

import pandas as pd

from tradingplatformpoc.district_heating_calculations import calculate_jan_feb_avg_heating_sold, \
    calculate_peak_day_avg_cons_kw, estimate_district_heating_price, exact_district_heating_price_for_month, \
    exact_effect_fee, get_base_marginal_price, get_grid_fee_for_month


class Test(TestCase):
    # Rough prices:
    # Jan - Feb: 0.55 + 0.66 + 0.10 = 1.31 SEK / kWh
    # Mar - Apr: 0.55 + 0.10 = 0.65 SEK / kWh
    # May - Sep: 0.33 + 0.10 = 0.45 SEK / kWh
    # Oct - Dec: 0.55 + 0.10 = 0.65 SEK / kWh

    def test_estimate_district_heating_price_jan(self):
        self.assertAlmostEqual(1.311891744, estimate_district_heating_price(datetime.datetime(2019, 1, 1)))

    def test_estimate_district_heating_price_feb(self):
        self.assertAlmostEqual(1.322548426, estimate_district_heating_price(datetime.datetime(2019, 2, 1)))

    def test_estimate_district_heating_price_mar(self):
        self.assertAlmostEqual(0.649462366, estimate_district_heating_price(datetime.datetime(2019, 3, 1)))

    def test_estimate_district_heating_price_apr(self):
        self.assertAlmostEqual(0.652777777, estimate_district_heating_price(datetime.datetime(2019, 4, 1)))

    def test_estimate_district_heating_price_may(self):
        self.assertAlmostEqual(0.429462366, estimate_district_heating_price(datetime.datetime(2019, 5, 1)))

    def test_estimate_district_heating_price_jun(self):
        self.assertAlmostEqual(0.432777777, estimate_district_heating_price(datetime.datetime(2019, 6, 1)))

    def test_estimate_district_heating_price_july(self):
        self.assertAlmostEqual(0.429462365, estimate_district_heating_price(datetime.datetime(2019, 7, 1)))

    def test_estimate_district_heating_price_aug(self):
        self.assertAlmostEqual(0.429462365, estimate_district_heating_price(datetime.datetime(2019, 8, 1)))

    def test_estimate_district_heating_price_sep(self):
        self.assertAlmostEqual(0.432777777, estimate_district_heating_price(datetime.datetime(2019, 9, 1)))

    def test_estimate_district_heating_price_oct(self):
        self.assertAlmostEqual(0.649462365, estimate_district_heating_price(datetime.datetime(2019, 10, 1)))

    def test_estimate_district_heating_price_nov(self):
        self.assertAlmostEqual(0.652777777, estimate_district_heating_price(datetime.datetime(2019, 11, 1)))

    def test_estimate_district_heating_price_dec(self):
        self.assertAlmostEqual(0.649462365, estimate_district_heating_price(datetime.datetime(2019, 12, 1)))

    def test_calculate_jan_feb_avg_heating_sold(self):
        """Test basic functionality of calculate_jan_feb_avg_heating_sold"""
        all_external_heating_sells = pd.Series()
        all_external_heating_sells[datetime.datetime(2019, 2, 1, 1)] = 50
        all_external_heating_sells[datetime.datetime(2019, 3, 1, 1)] = 100
        self.assertAlmostEqual(50, calculate_jan_feb_avg_heating_sold(all_external_heating_sells,
                                                                      datetime.datetime(2019, 3, 1, 1)))
        self.assertTrue(np.isnan(calculate_jan_feb_avg_heating_sold(all_external_heating_sells,
                                                                    datetime.datetime(2019, 2, 1, 1))))

    def test_calculate_peak_day_avg_cons_kw(self):
        """Test basic functionality of calculate_peak_day_avg_cons_kw"""
        all_external_heating_sells = pd.Series()
        all_external_heating_sells[datetime.datetime(2019, 3, 1, 1)] = 100
        all_external_heating_sells[datetime.datetime(2019, 3, 1, 2)] = 140
        all_external_heating_sells[datetime.datetime(2019, 3, 2, 1)] = 50
        all_external_heating_sells[datetime.datetime(2019, 3, 2, 2)] = 50
        all_external_heating_sells[datetime.datetime(2019, 3, 2, 3)] = 50
        self.assertAlmostEqual(10, calculate_peak_day_avg_cons_kw(all_external_heating_sells, 2019, 3))

    def test_get_base_marginal_price(self):
        """Test Marginal_Price_Value for summer/winter periods,
            Marginal_Price_Value in summer < Marginal_Price_Value in winter"""
        self.assertTrue(get_base_marginal_price(5) < get_base_marginal_price(2))

    def test_get_grid_fee_for_month(self):
        self.assertAlmostEqual(570.31506849, get_grid_fee_for_month(5, 2019, 10))

    def test_exact_effect_fee(self):
        self.assertAlmostEqual(185, exact_effect_fee(2.5))

    def test_exact_district_heating_price_for_month(self):
        self.assertAlmostEqual(793.81506849, exact_district_heating_price_for_month(10, 2019, 70, 5, 2.5))
