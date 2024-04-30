from datetime import datetime, timezone
from unittest import TestCase

import numpy as np

import pandas as pd

from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.trade import Resource
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between

SOME_DATETIME = datetime(2019, 2, 1, 1, tzinfo=timezone.utc)

DATETIME_ARRAY = hourly_datetime_array_between(datetime(2018, 12, 31, 23, tzinfo=timezone.utc),
                                               datetime(2020, 1, 31, 22, tzinfo=timezone.utc))

# To make tests consistent, set a random seed
np.random.seed(1)


class TestBlockAgent(TestCase):
    # Won't test exact values so don't need to set random seed
    elec_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    heat_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    static_digital_twin_cons = StaticDigitalTwin(1000.0, electricity_usage=pd.Series(elec_values, index=DATETIME_ARRAY),
                                                 space_heating_usage=pd.Series(heat_values, index=DATETIME_ARRAY))
    block_agent_cons = BlockAgent(digital_twin=static_digital_twin_cons)
    static_digital_twin_prod = StaticDigitalTwin(1000.0,
                                                 electricity_usage=-pd.Series(elec_values, index=DATETIME_ARRAY),
                                                 space_heating_usage=-pd.Series(heat_values, index=DATETIME_ARRAY))
    block_agent_prod = BlockAgent(digital_twin=static_digital_twin_prod)
    static_digital_twin_zeros = StaticDigitalTwin(1000.0,
                                                  electricity_usage=pd.Series(elec_values * 0, index=DATETIME_ARRAY),
                                                  space_heating_usage=pd.Series(heat_values * 0, index=DATETIME_ARRAY))
    block_agent_zeros = BlockAgent(digital_twin=static_digital_twin_zeros)

    def test_get_actual_usage(self):
        """Test basic functionality of BlockAgent's get_actual_usage method."""
        usage_consumer = self.block_agent_cons.get_actual_usage_for_resource(SOME_DATETIME, Resource.ELECTRICITY)
        self.assertFalse(np.isnan(usage_consumer))
        self.assertTrue(usage_consumer > 0)
        usage_producer = self.block_agent_prod.get_actual_usage_for_resource(SOME_DATETIME, Resource.ELECTRICITY)
        self.assertFalse(np.isnan(usage_producer))
        self.assertTrue(usage_producer < 0)
