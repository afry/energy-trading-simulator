from datetime import datetime, timedelta, timezone
from unittest import TestCase

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

import polars as pl

from tradingplatformpoc.compress import bz2_decompress_pickle
from tradingplatformpoc.data.preprocessing import read_temperature_data
from tradingplatformpoc.generate_data.generate_mock_data import DATA_PATH
from tradingplatformpoc.generate_data.generation_functions.common import is_day_before_major_holiday_sweden, \
    is_major_holiday_sweden
from tradingplatformpoc.generate_data.generation_functions.non_residential.commercial import \
    simulate_commercial_area_cooling
from tradingplatformpoc.generate_data.generation_functions.non_residential.common import \
    probability_of_0_space_heating, simulate_space_heating
from tradingplatformpoc.generate_data.generation_functions.non_residential.school import \
    get_school_heating_consumption_hourly_factor, is_break
from tradingplatformpoc.generate_data.generation_functions.residential.electricity import \
    simulate_series_with_log_energy_model
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

    def test_non_residential_heating(self):
        """
        Test space heating data generation.
        """
        input_df = read_temperature_data()
        lazy_inputs = pl.from_pandas(input_df).lazy()
        heating = simulate_space_heating(1000, 1, lazy_inputs, 25,
                                         get_school_heating_consumption_hourly_factor, len(input_df.index))
        output_pd_df = heating.collect().to_pandas()
        self.assertFalse((output_pd_df['value'] < 0).any())
        # Shouldn't be many 0s for Nov-Dec, for example
        self.assertTrue((output_pd_df['value'][output_pd_df['datetime'].dt.month > 10] == 0).sum() < 100)

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

        unscaled_simulated_values_for_area = simulate_series_with_log_energy_model(pl.from_pandas(input_df),
                                                                                   random_seed, model)
        values_pd = unscaled_simulated_values_for_area.to_pandas().value
        self.assertAlmostEqual(358.64245460289527, values_pd[:8766].sum())
        self.assertAlmostEqual(0.286418874824197, values_pd[0])

    def test_all_parameters_match_true(self):
        """When agents do not contain any commercial buildings, it shouldn't matter that commercial mock data generation
        constants are different."""
        agent_1 = {'Name': 'ResidentialBlockAgentB1', 'FractionCommercial': 0.0}
        agent_2 = agent_1.copy()
        mock_data_constants_1 = {'CommercialElecKwhPerYearM2': 50}
        mock_data_constants_2 = {'CommercialElecKwhPerYearM2': 60}
        self.assertTrue(all_parameters_match(agent_1, agent_2, mock_data_constants_1, mock_data_constants_2))

    def test_all_parameters_match_false(self):
        """When agents do contain commercial buildings, it should matter that commercial mock data generation
        constants are different."""
        agent_1 = {'Name': 'ResidentialBlockAgentB1', 'FractionCommercial': 0.1}
        agent_2 = agent_1.copy()
        mock_data_constants_1 = {'CommercialElecKwhPerYearM2': 50}
        mock_data_constants_2 = {'CommercialElecKwhPerYearM2': 60}
        self.assertFalse(all_parameters_match(agent_1, agent_2, mock_data_constants_1, mock_data_constants_2))

    def test_is_break(self):
        """Simple test of is_break method. Using UTC just because it is the most convenient."""
        self.assertTrue(is_break(datetime(2019, 7, 1, tzinfo=timezone.utc)))
        self.assertFalse(is_break(datetime(2019, 9, 1, tzinfo=timezone.utc)))

    def test_commercial_cooling(self):
        # Set the start date and time
        start_date = datetime(2019, 1, 1, 0, 0, 0)

        # Set the number of hours for the full year
        num_hours_in_year = 365 * 24

        # Create a list of datetime values with hourly increments
        date_values = [start_date + timedelta(hours=i) for i in range(num_hours_in_year)]

        input_df = pd.DataFrame({'datetime': date_values})
        cooling = simulate_commercial_area_cooling(1000, 1, pl.from_pandas(input_df).lazy(), 34, 0.2, num_hours_in_year)
        output_pd_df = cooling.collect().to_pandas()
        self.assertAlmostEqual(34000, output_pd_df['value'].sum())
        self.assertEqual(0.0, output_pd_df['value'][0])  # no cooling consumption during winter
        self.assertFalse((output_pd_df['value'] < 0).any())

    def test_binomial_model(self):
        self.assertAlmostEqual(0.011051883541022711, probability_of_0_space_heating(7))
