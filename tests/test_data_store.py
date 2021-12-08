import json

from unittest import TestCase
from tradingplatformpoc import data_store


class TestDataStore(TestCase):

    def __init__(self, *args, **kwargs):
        super(TestDataStore, self).__init__(*args, **kwargs)
        with open("../data/jonstaka.json", "r") as jsonfile:
            config_data = json.load(jsonfile)

        self.data_store_entity = data_store.DataStore(config_data=config_data["AreaInfo"])

    def test_get_nordpool_price_for_period(self):
        self.assertEqual(0.51871, self.data_store_entity.get_nordpool_price_for_period("2019-02-01 01:00:00"))

    def test_retail_price(self):
        self.assertEqual(0.99871, self.data_store_entity.get_retail_price("2019-02-01 01:00:00"))

    def test_wholesale_price(self):
        self.assertEqual(0.56871, self.data_store_entity.get_wholesale_price("2019-02-01 01:00:00"))

    def test_get_tornet_household_electricity_consumed(self):
        self.assertEqual(206.2577964869327,
                         self.data_store_entity.get_tornet_household_electricity_consumed("2019-02-01 01:00:00"))

    def test_get_coop_electricity_consumed(self):
        self.assertEqual(130.71967582084125,
                         self.data_store_entity.get_coop_electricity_consumed("2019-02-01 01:00:00"))

    def test_get_tornet_pv_produced(self):
        self.assertEqual(4458.9793248000005, self.data_store_entity.get_tornet_pv_produced("2019-08-01 11:00:00"))

    def test_get_coop_pv_produced(self):
        self.assertEqual(29.27232, self.data_store_entity.get_coop_pv_produced("2019-08-01 11:00:00"))

    def test_get_energy_mock_timestamps(self):
        test = self.data_store_entity.get_trading_periods()
        # Need to figure out some reasonable assertion for this unit test. Length of list?
        self.assertEqual(1, 1)