from datetime import datetime, timezone
from unittest import TestCase

import numpy as np

import pandas as pd
from pandas import DatetimeIndex

from pkg_resources import resource_filename

from tests import utility_test_objects

from tradingplatformpoc import data_store
from tradingplatformpoc.bid import Resource
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between

FEB_1_1_AM = datetime(2019, 2, 1, 1, 0, 0, tzinfo=timezone.utc)

DATETIME_ARRAY = hourly_datetime_array_between(datetime(2018, 12, 31, 23, tzinfo=timezone.utc),
                                               datetime(2020, 1, 31, 22, tzinfo=timezone.utc))
CONSTANT_NORDPOOL_PRICE = 0.6  # Doesn't matter what this is
ONES_SERIES = pd.Series(np.ones(shape=len(DATETIME_ARRAY)), index=DATETIME_ARRAY)


class TestDataStore(TestCase):
    data_store_entity = data_store.DataStore(config_area_info=utility_test_objects.AREA_INFO,
                                             nordpool_data=ONES_SERIES * CONSTANT_NORDPOOL_PRICE,
                                             irradiation_data=ONES_SERIES,
                                             temperature_data=ONES_SERIES,
                                             grid_carbon_intensity=ONES_SERIES)

    def test_get_nordpool_price_for_period(self):
        """Test that what we put into data_store is the same as we get out"""
        self.assertEqual(CONSTANT_NORDPOOL_PRICE,
                         self.data_store_entity.get_nordpool_price_for_period(FEB_1_1_AM))

    def test_estimated_retail_price_greater_than_wholesale_price(self):
        """Test that the retail price is always greater than the wholesale price, even without including taxes"""
        # May want to test for other resources than ELECTRICITY
        for dt in DATETIME_ARRAY:
            retail_price = self.data_store_entity.get_estimated_retail_price(dt, Resource.ELECTRICITY,
                                                                             include_tax=False)
            wholesale_price = self.data_store_entity.get_estimated_wholesale_price(dt, Resource.ELECTRICITY)
            self.assertTrue(retail_price > wholesale_price)

    def test_retail_price_offset(self):
        """
        Test that different tax rates and grid fees are reflected in the price we get from get_estimated_retail_price.
        """
        data_store_2 = data_store.DataStore(config_area_info={"DefaultPVEfficiency": 0.165,
                                                              "HeatTransferLoss": 0.05,
                                                              "ElectricityTax": 1.5,
                                                              "ElectricityGridFee": 0.5,
                                                              "ElectricityTaxInternal": 0,
                                                              "ElectricityGridFeeInternal": 0},
                                            nordpool_data=ONES_SERIES * CONSTANT_NORDPOOL_PRICE,
                                            irradiation_data=ONES_SERIES,
                                            temperature_data=ONES_SERIES,
                                            grid_carbon_intensity=ONES_SERIES)

        # Comparing gross prices
        price_for_normal_ds = self.data_store_entity.get_estimated_retail_price(FEB_1_1_AM, Resource.ELECTRICITY,
                                                                                include_tax=False)
        self.assertAlmostEqual(0.73, price_for_normal_ds)
        self.assertAlmostEqual(1.1, data_store_2.get_estimated_retail_price(FEB_1_1_AM, Resource.ELECTRICITY,
                                                                            include_tax=False))
        # Comparing net prices
        price_for_normal_ds = self.data_store_entity.get_estimated_retail_price(FEB_1_1_AM, Resource.ELECTRICITY,
                                                                                include_tax=True)
        self.assertAlmostEqual(1.09, price_for_normal_ds)
        self.assertAlmostEqual(2.6, data_store_2.get_estimated_retail_price(FEB_1_1_AM, Resource.ELECTRICITY,
                                                                            include_tax=True))

    def test_get_estimated_price_for_non_implemented_resource(self):
        with self.assertRaises(RuntimeError):
            self.data_store_entity.get_estimated_retail_price(FEB_1_1_AM, Resource.COOLING, include_tax=False)

    def test_read_electricitymap_csv(self):
        """Test that the CSV file with ElectricityMap carbon intensity data reads correctly."""
        file_path = resource_filename("tradingplatformpoc.data", "electricity_co2equivalents_year2019.csv")
        data = data_store.read_electricitymap_csv(file_path)
        self.assertTrue(data.shape[0] > 0)
        self.assertIsInstance(data.index, DatetimeIndex)

    def test_read_outdoor_temperature_csv(self):
        """Test that the CSV file with Vetelangden temperature data reads correctly."""
        file_path = resource_filename("tradingplatformpoc.data", "temperature_vetelangden.csv")
        data = data_store.read_outdoor_temperature(file_path)
        self.assertTrue(data.shape[0] > 0)
        self.assertIsInstance(data.index, DatetimeIndex)

    def test_add_external_heating_sell(self):
        ds = data_store.DataStore(config_area_info=utility_test_objects.AREA_INFO,
                                  nordpool_data=ONES_SERIES * CONSTANT_NORDPOOL_PRICE,
                                  irradiation_data=ONES_SERIES, temperature_data=ONES_SERIES,
                                  grid_carbon_intensity=ONES_SERIES)
        self.assertEqual(0, len(ds.all_external_heating_sells))
        ds.add_external_heating_sell(FEB_1_1_AM, 50.0)
        self.assertEqual(1, len(ds.all_external_heating_sells))

    def test_add_external_heating_sell_where_already_exists(self):
        ds = data_store.DataStore(config_area_info=utility_test_objects.AREA_INFO,
                                  nordpool_data=ONES_SERIES * CONSTANT_NORDPOOL_PRICE,
                                  irradiation_data=ONES_SERIES, temperature_data=ONES_SERIES,
                                  grid_carbon_intensity=ONES_SERIES)
        self.assertEqual(0, len(ds.all_external_heating_sells))
        ds.add_external_heating_sell(FEB_1_1_AM, 50.0)
        self.assertEqual(1, len(ds.all_external_heating_sells))
        self.assertAlmostEqual(50.0, ds.all_external_heating_sells[FEB_1_1_AM])
        # Now add again for the same period, with different value
        # First test that this logs as expectec
        with self.assertLogs() as captured:
            ds.add_external_heating_sell(FEB_1_1_AM, 70.0)
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(captured.records[0].levelname, 'WARNING')
        # Then test that the result of the operation is expected
        self.assertEqual(1, len(ds.all_external_heating_sells))
        self.assertAlmostEqual(70.0, ds.all_external_heating_sells[FEB_1_1_AM])

    def test_calculate_consumption_this_month(self):
        """Test basic functionality of calculate_consumption_this_month"""
        ds = data_store.DataStore(config_area_info=utility_test_objects.AREA_INFO,
                                  nordpool_data=ONES_SERIES * CONSTANT_NORDPOOL_PRICE,
                                  irradiation_data=ONES_SERIES, temperature_data=ONES_SERIES,
                                  grid_carbon_intensity=ONES_SERIES)
        ds.add_external_heating_sell(FEB_1_1_AM, 50)
        ds.add_external_heating_sell(datetime(2019, 3, 1, 1, tzinfo=timezone.utc), 100)
        self.assertAlmostEqual(50, ds.calculate_consumption_this_month(2019, 2))
        self.assertAlmostEqual(0, ds.calculate_consumption_this_month(2019, 4))

    def test_get_exact_retail_price_heating(self):
        """Test basic functionality of get_exact_retail_price for HEATING"""
        ds = data_store.DataStore(config_area_info=utility_test_objects.AREA_INFO,
                                  nordpool_data=ONES_SERIES * CONSTANT_NORDPOOL_PRICE,
                                  irradiation_data=ONES_SERIES, temperature_data=ONES_SERIES,
                                  grid_carbon_intensity=ONES_SERIES)
        ds.add_external_heating_sell(datetime(2019, 2, 1, 1, tzinfo=timezone.utc), 100)
        ds.add_external_heating_sell(datetime(2019, 3, 1, 1, tzinfo=timezone.utc), 100)
        ds.add_external_heating_sell(datetime(2019, 3, 1, 2, tzinfo=timezone.utc), 140)
        ds.add_external_heating_sell(datetime(2019, 3, 2, 1, tzinfo=timezone.utc), 50)
        ds.add_external_heating_sell(datetime(2019, 3, 2, 2, tzinfo=timezone.utc), 50)
        ds.add_external_heating_sell(datetime(2019, 3, 2, 3, tzinfo=timezone.utc), 50)
        self.assertAlmostEqual(26.546859852476288,
                               ds.get_exact_retail_price(datetime(2019, 3, 2, 3), Resource.HEATING, include_tax=True))
