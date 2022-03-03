import datetime
from unittest import TestCase

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

from tests import utility_test_objects

from tradingplatformpoc import simulation_runner
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.simulation_runner import get_quantity_heating_sold_by_external_grid
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between


class Test(TestCase):
    mock_datas_file_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
    fake_config = {'Agents': []}
    empty_data_store = DataStore(utility_test_objects.AREA_INFO, pd.Series(dtype=float), pd.Series(dtype=float),
                                 pd.Series(dtype=float))

    def test_initialize_agents(self):
        energy_data_csv_path = resource_filename("tradingplatformpoc.data", "full_mock_energy_data.csv")
        with self.assertRaises(RuntimeError):
            simulation_runner.initialize_agents(self.empty_data_store, self.fake_config, pd.DataFrame(),
                                                energy_data_csv_path)

    def test_get_quantity_heating_sold_by_external_grid(self):
        """Test that get_quantity_heating_sold_by_external_grid doesn't break when there are no external trades."""
        self.assertEqual(0, get_quantity_heating_sold_by_external_grid([]))

    def test_get_external_heating_prices_from_empty_data_store(self):
        """
        When trying to calculate external heating prices using an empty DataStore, NaNs should be returned for exact
        prices, and warnings should be logged.
        """
        with self.assertLogs() as captured:
            estimated_retail_heating_prices_by_year_and_month, \
                estimated_wholesale_heating_prices_by_year_and_month, \
                exact_retail_heating_prices_by_year_and_month, \
                exact_wholesale_heating_prices_by_year_and_month = simulation_runner.get_external_heating_prices(
                    self.empty_data_store, hourly_datetime_array_between(
                        datetime.datetime(2019, 2, 1), datetime.datetime(2019, 2, 2)))
        self.assertTrue(len(captured.records) > 0)
        log_levels_captured = [rec.levelname for rec in captured.records]
        self.assertTrue('WARNING' in log_levels_captured)

        self.assertTrue(np.isnan(exact_retail_heating_prices_by_year_and_month[(2019, 2)]))
        self.assertTrue(np.isnan(exact_wholesale_heating_prices_by_year_and_month[(2019, 2)]))
        self.assertFalse(np.isnan(estimated_retail_heating_prices_by_year_and_month[(2019, 2)]))
        self.assertFalse(np.isnan(estimated_wholesale_heating_prices_by_year_and_month[(2019, 2)]))
