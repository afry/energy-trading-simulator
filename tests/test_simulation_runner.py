from unittest import TestCase

import pandas as pd

from pkg_resources import resource_filename

from tests import utility_test_objects

from tradingplatformpoc import simulation_runner
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.simulation_runner import get_quantity_heating_sold_by_external_grid


class Test(TestCase):
    mock_datas_file_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
    fake_config = {'Agents': []}

    def test_get_generated_mock_data_when_doesnt_exist(self):
        """Test that when trying to fetch mock data for a set of residential building agents that doesn't exist, an
        error is raised."""
        with self.assertRaises(RuntimeError):
            simulation_runner.get_generated_mock_data(self.fake_config, self.mock_datas_file_path)

    def test_initialize_agents(self):
        energy_data_csv_path = resource_filename("tradingplatformpoc.data", "full_mock_energy_data.csv")
        school_data_csv_path = resource_filename("tradingplatformpoc.data", "school_electricity_consumption.csv")
        empty_data_store = DataStore(utility_test_objects.AREA_INFO, pd.Series(dtype=float), pd.Series(dtype=float),
                                     pd.Series(dtype=float))
        with self.assertRaises(RuntimeError):
            simulation_runner.initialize_agents(empty_data_store, self.fake_config, pd.DataFrame(),
                                                energy_data_csv_path, school_data_csv_path)

    def test_get_quantity_heating_sold_by_external_grid(self):
        """Test that get_quantity_heating_sold_by_external_grid doesn't break when there are no external trades."""
        self.assertEqual(0, get_quantity_heating_sold_by_external_grid([]))
