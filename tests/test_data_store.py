from datetime import datetime

from unittest import TestCase

import numpy as np
import pandas as pd
from pandas import DatetimeIndex
from pkg_resources import resource_filename

from tradingplatformpoc import data_store
from tradingplatformpoc.trading_platform_utils import datetime_array_between


AREA_INFO = {
    "ParkPVArea": 24324.3,
    "StorePVArea": 320,
    "PVEfficiency": 0.165
}
DATETIME_ARRAY = datetime_array_between(datetime(2018, 12, 31, 23), datetime(2020, 1, 31, 22))
CONSTANT_NORDPOOL_PRICE = 0.6  # Doesn't matter what this is
ONES_SERIES = pd.Series(np.ones(shape=len(DATETIME_ARRAY)), index=DATETIME_ARRAY)


class TestDataStore(TestCase):
    data_store_entity = data_store.DataStore(config_area_info=AREA_INFO,
                                             nordpool_data=ONES_SERIES * CONSTANT_NORDPOOL_PRICE,
                                             irradiation_data=ONES_SERIES)

    def test_get_nordpool_price_for_period(self):
        """Test that what we put into data_store is the same as we get out"""
        self.assertEqual(CONSTANT_NORDPOOL_PRICE,
                         self.data_store_entity.get_nordpool_price_for_period(datetime(2019, 2, 1, 1, 0, 0)))

    def test_retail_price_greater_than_wholesale_price(self):
        """Test that the retail price is always greater than the wholesale price"""
        for dt in DATETIME_ARRAY:
            retail_price = self.data_store_entity.get_retail_price(dt)
            wholesale_price = self.data_store_entity.get_wholesale_price(dt)
            self.assertTrue(retail_price > wholesale_price)

    def test_read_school_csv(self):
        """Test that the CSV file with school energy data reads correctly."""
        file_path = resource_filename("tradingplatformpoc.data", "school_electricity_consumption.csv")
        school_energy_data = data_store.read_school_energy_consumption_csv(file_path)
        self.assertTrue(school_energy_data.shape[0] > 0)
        self.assertIsInstance(school_energy_data.index, DatetimeIndex)
