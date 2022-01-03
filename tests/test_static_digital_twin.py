import json
from datetime import datetime
from unittest import TestCase

from tradingplatformpoc import data_store
from tradingplatformpoc.bid import Resource
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin

with open("../tradingplatformpoc/data/jonstaka.json", "r") as jsonfile:
    config_data = json.load(jsonfile)
data_store_entity = data_store.DataStore(config_area_info=config_data["AreaInfo"])


class TestStaticDigitalTwin(TestCase):
    building_digital_twin = StaticDigitalTwin(electricity_usage=data_store_entity.tornet_household_elec_cons,
                                              heating_usage=data_store_entity.tornet_heat_cons)
    grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=data_store_entity.coop_elec_cons,
                                                   heating_usage=data_store_entity.coop_heat_cons,
                                                   electricity_production=data_store_entity.coop_pv_prod)
    pv_digital_twin = StaticDigitalTwin(electricity_production=data_store_entity.tornet_park_pv_prod)

    def test_get_tornet_household_electricity_consumed(self):
        self.assertAlmostEqual(206.25779648693268,
                               self.building_digital_twin.get_consumption(datetime(2019, 2, 1, 1, 0, 0),
                                                                          Resource.ELECTRICITY))

    def test_get_coop_electricity_consumed(self):
        self.assertAlmostEqual(130.71967582084125,
                               self.grocery_store_digital_twin.get_consumption(datetime(2019, 2, 1, 1, 0, 0),
                                                                               Resource.ELECTRICITY))

    def test_get_tornet_pv_produced(self):
        self.assertAlmostEqual(2225.0896668,
                               self.pv_digital_twin.get_production(datetime(2019, 8, 1, 11, 0, 0),
                                                                   Resource.ELECTRICITY))

    def test_get_coop_pv_produced(self):
        self.assertAlmostEqual(29.27232, self.grocery_store_digital_twin.get_production(datetime(2019, 8, 1, 11, 0, 0),
                                                                                        Resource.ELECTRICITY))
