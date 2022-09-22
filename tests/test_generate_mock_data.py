from datetime import datetime, timezone
from unittest import TestCase

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

import statsmodels.api as sm

from tradingplatformpoc import generate_mock_data
from tradingplatformpoc.generate_mock_data import DATA_PATH, is_day_before_major_holiday_sweden, \
    is_major_holiday_sweden, simulate_school_area_space_heating, simulate_series
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
        """
        Test space heating data generation.
        """
        random_seed = 10
        rng = np.random.default_rng(random_seed)
        datetimes = hourly_datetime_array_between(datetime(2018, 12, 31, 23), datetime(2020, 1, 31, 22))
        input_df = pd.DataFrame({'datetime': datetimes,
                                 'temperature': rng.normal(loc=8, scale=8, size=len(datetimes))})
        self.assertAlmostEqual(-0.8267075925242562, input_df.temperature[0])
        input_df.set_index('datetime', inplace=True)
        space_heating = simulate_school_area_space_heating(100, random_seed, input_df)
        self.assertAlmostEqual(2500, space_heating[:8766].sum())
        self.assertAlmostEqual(0.5805394474233916, space_heating[0])

    def test_simulate_residential_electricity(self):
        """
        Test residential electricity generation.
        """
        model = sm.load(resource_filename(DATA_PATH, 'models/household_electricity_model.pickle'))
        random_seed = 10
        rng = np.random.default_rng(random_seed)
        datetimes = hourly_datetime_array_between(datetime(2019, 12, 31, 23, tzinfo=timezone.utc),
                                                  datetime(2020, 1, 31, 22, tzinfo=timezone.utc))
        input_df = pd.DataFrame({'datetime': datetimes,
                                 'temperature': rng.normal(loc=8, scale=8, size=len(datetimes))})
        input_df['hour_of_day'] = input_df['datetime'].dt.hour + 1
        input_df['day_of_week'] = input_df['datetime'].dt.dayofweek + 1
        input_df['day_of_month'] = input_df['datetime'].dt.day
        input_df['month_of_year'] = input_df['datetime'].dt.month
        input_df['major_holiday'] = input_df['datetime'].apply(lambda dt: is_major_holiday_sweden(dt)).\
            astype(bool)
        input_df['pre_major_holiday'] = input_df['datetime'].apply(lambda dt: is_day_before_major_holiday_sweden(dt)).\
            astype(bool)

        unscaled_simulated_values_for_area = simulate_series(input_df, random_seed, model)
        self.assertAlmostEqual(358.64245460289527, unscaled_simulated_values_for_area[:8766].sum())
        self.assertAlmostEqual(0.286418874824197, unscaled_simulated_values_for_area[0])
