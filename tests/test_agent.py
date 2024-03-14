from datetime import datetime, timezone
from unittest import TestCase

import numpy as np

import pandas as pd

from tests import utility_test_objects

from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between

SOME_DATETIME = datetime(2019, 2, 1, 1, tzinfo=timezone.utc)

MAX_NORDPOOL_PRICE = 4.0

MIN_NORDPOOL_PRICE = 0.1
DATETIME_ARRAY = hourly_datetime_array_between(datetime(2018, 12, 31, 23, tzinfo=timezone.utc),
                                               datetime(2020, 1, 31, 22, tzinfo=timezone.utc))

# To make tests consistent, set a random seed
np.random.seed(1)
# Create data
nordpool_values = np.random.uniform(MIN_NORDPOOL_PRICE, MAX_NORDPOOL_PRICE, len(DATETIME_ARRAY))
irradiation_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
carbon_values = np.ones(shape=len(DATETIME_ARRAY))

# Read CSV files
irradiation_data = pd.Series(irradiation_values, index=DATETIME_ARRAY)
external_price_data = pd.Series(nordpool_values, index=DATETIME_ARRAY)

area_info = utility_test_objects.AREA_INFO
heat_pricing: HeatingPrice = HeatingPrice(
    heating_wholesale_price_fraction=area_info['ExternalHeatingWholesalePriceFraction'],
    heat_transfer_loss=area_info["HeatTransferLoss"])
electricity_pricing: ElectricityPrice = ElectricityPrice(
    elec_wholesale_offset=area_info['ExternalElectricityWholesalePriceOffset'],
    elec_tax=area_info["ElectricityTax"],
    elec_grid_fee=area_info["ElectricityGridFee"],
    elec_tax_internal=area_info["ElectricityTaxInternal"],
    elec_grid_fee_internal=area_info["ElectricityGridFeeInternal"],
    nordpool_data=external_price_data)


class TestBlockAgent(TestCase):
    # Won't test exact values so don't need to set random seed
    elec_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    heat_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    static_digital_twin_cons = StaticDigitalTwin(1000.0, electricity_usage=pd.Series(elec_values, index=DATETIME_ARRAY),
                                                 space_heating_usage=pd.Series(heat_values, index=DATETIME_ARRAY))
    block_agent_cons = BlockAgent(True, heat_pricing=heat_pricing, electricity_pricing=electricity_pricing,
                                  digital_twin=static_digital_twin_cons, can_sell_heat_to_external=False)
    static_digital_twin_prod = StaticDigitalTwin(1000.0,
                                                 electricity_usage=-pd.Series(elec_values, index=DATETIME_ARRAY),
                                                 space_heating_usage=-pd.Series(heat_values, index=DATETIME_ARRAY))
    block_agent_prod = BlockAgent(True, heat_pricing=heat_pricing, electricity_pricing=electricity_pricing,
                                  digital_twin=static_digital_twin_prod, can_sell_heat_to_external=False)
    static_digital_twin_zeros = StaticDigitalTwin(1000.0,
                                                  electricity_usage=pd.Series(elec_values * 0, index=DATETIME_ARRAY),
                                                  space_heating_usage=pd.Series(heat_values * 0, index=DATETIME_ARRAY))
    block_agent_zeros = BlockAgent(True, heat_pricing=heat_pricing, electricity_pricing=electricity_pricing,
                                   digital_twin=static_digital_twin_zeros, can_sell_heat_to_external=False)

    def test_get_actual_usage(self):
        """Test basic functionality of BlockAgent's get_actual_usage method."""
        usage_consumer = self.block_agent_cons.get_actual_usage_for_resource(SOME_DATETIME, Resource.ELECTRICITY)
        self.assertFalse(np.isnan(usage_consumer))
        self.assertTrue(usage_consumer > 0)
        usage_producer = self.block_agent_prod.get_actual_usage_for_resource(SOME_DATETIME, Resource.ELECTRICITY)
        self.assertFalse(np.isnan(usage_producer))
        self.assertTrue(usage_producer < 0)
