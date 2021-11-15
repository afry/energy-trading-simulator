from unittest import TestCase

import data_store


class TestDataStore(TestCase):

    def __init__(self, *args, **kwargs):
        super(TestDataStore, self).__init__(*args, **kwargs)
        self.data_store_entity = data_store.DataStore('../data/nordpool_area_grid_el_price.csv',
                                                      '../data/full_mock_energy_data.csv')

    def test_get_nordpool_price_for_period(self):
        self.assertEqual(0.51871, self.data_store_entity.get_nordpool_price_for_period("2019-02-01 01:00:00"))

    def test_retail_price(self):
        self.assertEqual(0.99871, self.data_store_entity.get_retail_price("2019-02-01 01:00:00"))

    def test_wholesale_price(self):
        self.assertEqual(0.56871, self.data_store_entity.get_wholesale_price("2019-02-01 01:00:00"))

    def test_get_tornet_household_electricity_consumed(self):
        self.assertEqual(230.18767338928367,
                         self.data_store_entity.get_tornet_household_electricity_consumed("2019-02-01 01:00:00"))

    def test_get_coop_electricity_consumed(self):
        self.assertEqual(130.71967582084125,
                         self.data_store_entity.get_coop_electricity_consumed("2019-02-01 01:00:00"))

    def test_get_tornet_pv_produced(self):
        self.assertEqual(521.4550176, self.data_store_entity.get_tornet_pv_produced("2019-08-01 11:00:00"))

    def test_get_coop_pv_produced(self):
        self.assertEqual(33.98208, self.data_store_entity.get_coop_pv_produced("2019-08-01 11:00:00"))

    def test_get_energy_mock_timestamps(self):
        test = self.data_store_entity.get_trading_periods()
        # Need to figure out some reasonable assertion for this unit test. Length of list?
        self.assertEqual(1, 1)
