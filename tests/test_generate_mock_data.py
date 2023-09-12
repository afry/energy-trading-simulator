from datetime import datetime, timezone
from unittest import TestCase

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

import polars as pl

from tradingplatformpoc.compress import bz2_decompress_pickle
from tradingplatformpoc.config.access_config import read_param_specs
from tradingplatformpoc.generate_data.generate_mock_data import DATA_PATH
from tradingplatformpoc.generate_data.generation_functions.common import is_day_before_major_holiday_sweden, \
    is_major_holiday_sweden
from tradingplatformpoc.generate_data.generation_functions.non_residential.common import simulate_space_heating
from tradingplatformpoc.generate_data.generation_functions.non_residential.school import \
    get_school_heating_consumption_hourly_factor
from tradingplatformpoc.generate_data.generation_functions.residential.residential import simulate_series
from tradingplatformpoc.generate_data.mock_data_utils import all_parameters_match
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between


class Test(TestCase):

    def test_is_major_holiday_sweden(self):
        xmas_eve = pd.Timestamp('2017-12-24T01', tz='UTC')
        self.assertTrue(is_major_holiday_sweden(xmas_eve))
        xmas_eve_in_tz_far_away = pd.Timestamp('2017-12-24T01', tz='Australia/Sydney')
        self.assertFalse(is_major_holiday_sweden(xmas_eve_in_tz_far_away))

    def test_is_day_before_major_holiday_sweden(self):
        new_years_eve = pd.Timestamp('2017-12-31T01', tz='UTC')
        self.assertTrue(is_day_before_major_holiday_sweden(new_years_eve))
        new_years_eve_in_tz_far_away = pd.Timestamp('2017-12-31T01', tz='Australia/Sydney')
        self.assertFalse(is_day_before_major_holiday_sweden(new_years_eve_in_tz_far_away))

    def test_simulate_school_area_space_heating(self):
        """
        Test space heating data generation.
        """
        random_seed = 10
        rng = np.random.default_rng(random_seed)
        datetimes = hourly_datetime_array_between(datetime(2018, 12, 31, 23), datetime(2020, 1, 31, 22))
        input_df = pl.DataFrame({'datetime': datetimes,
                                 'temperature': rng.normal(loc=8, scale=8, size=len(datetimes))})
        self.assertAlmostEqual(-0.8267075925242562, input_df['temperature'][0])
        school_space_heat_kwh_per_year_m2_default = \
            read_param_specs(['MockDataConstants'])['MockDataConstants']['SchoolSpaceHeatKwhPerYearM2']['default']
        space_heating = simulate_space_heating(100, random_seed, input_df.lazy(),
                                               school_space_heat_kwh_per_year_m2_default,
                                               get_school_heating_consumption_hourly_factor, len(datetimes))
        space_heating_pd = space_heating.collect().to_pandas()
        self.assertAlmostEqual(2500, space_heating_pd.value[:8766].sum())
        self.assertAlmostEqual(0.7098387777531893, space_heating_pd.value[0])

    def test_simulate_residential_electricity(self):
        """
        Test residential electricity generation.
        """
        model = bz2_decompress_pickle(resource_filename(DATA_PATH, 'models/household_electricity_model.pbz2'))
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

        unscaled_simulated_values_for_area = simulate_series(pl.from_pandas(input_df), random_seed, model)
        values_pd = unscaled_simulated_values_for_area.to_pandas().value
        self.assertAlmostEqual(358.64245460289527, values_pd[:8766].sum())
        self.assertAlmostEqual(0.286418874824197, values_pd[0])

    def test_all_parameters_match_true(self):
        """When agents do not contain any commercial buildings, it shouldn't matter that commercial mock data generation
        constants are different."""
        agent_1 = {'Name': 'ResidentialBuildingAgentB1', 'FractionCommercial': 0.0}
        agent_2 = agent_1.copy()
        mock_data_constants_1 = {'CommercialElecKwhPerYearM2': 50}
        mock_data_constants_2 = {'CommercialElecKwhPerYearM2': 60}
        self.assertTrue(all_parameters_match(agent_1, agent_2, mock_data_constants_1, mock_data_constants_2))

    def test_all_parameters_match_false(self):
        """When agents do contain commercial buildings, it should matter that commercial mock data generation
        constants are different."""
        agent_1 = {'Name': 'ResidentialBuildingAgentB1', 'FractionCommercial': 0.1}
        agent_2 = agent_1.copy()
        mock_data_constants_1 = {'CommercialElecKwhPerYearM2': 50}
        mock_data_constants_2 = {'CommercialElecKwhPerYearM2': 60}
        self.assertFalse(all_parameters_match(agent_1, agent_2, mock_data_constants_1, mock_data_constants_2))
