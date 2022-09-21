import timeit
from datetime import datetime
from unittest import TestCase

import numpy as np
import pandas as pd
import polars as pl

from tradingplatformpoc import generate_mock_data
from tradingplatformpoc.generate_mock_data import simulate_space_heating
from tradingplatformpoc.mock_data_generation_functions import get_school_heating_consumption_hourly_factor
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between


class Test(TestCase):

    def test_is_major_holiday_sweden(self):
        xmas_eve = pd.Timestamp('2017-12-24T01', tz='UTC')
        self.assertTrue(generate_mock_data.is_major_holiday_sweden(xmas_eve))
        xmas_eve_in_tz_far_away = pd.Timestamp('2017-12-24T01', tz='Australia/Sydney')
        self.assertFalse(generate_mock_data.is_major_holiday_sweden(xmas_eve_in_tz_far_away))

    def test_is_day_before_major_holiday_sweden(self):
        new_years_eve = pd.Timestamp('2017-12-31T01', tz='UTC')
        self.assertTrue(generate_mock_data.is_day_before_major_holiday_sweden(new_years_eve))
        new_years_eve_in_tz_far_away = pd.Timestamp('2017-12-31T01', tz='Australia/Sydney')
        self.assertFalse(generate_mock_data.is_day_before_major_holiday_sweden(new_years_eve_in_tz_far_away))

    def test_simulate_school_area_space_heating(self):
        random_seed = 10
        rng = np.random.default_rng(random_seed)
        datetimes = hourly_datetime_array_between(datetime(2018, 12, 31, 23), datetime(2020, 1, 31, 22))
        input_df = pl.DataFrame({'datetime': datetimes,
                                 'temperature': rng.normal(loc=8, scale=8, size=len(datetimes))})
        start_time = timeit.default_timer()
        for i in range(100):
            _result = simulate_space_heating(100, random_seed, input_df, 1.0,
                                             get_school_heating_consumption_hourly_factor)
        print(timeit.default_timer() - start_time)
