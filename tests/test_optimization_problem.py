import datetime
import logging
from unittest import TestCase

import pandas as pd

from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.simulation_runner.chalmers_interface import add_value_per_agent_to_dict, \
    get_power_transfers
from tradingplatformpoc.simulation_runner.optimization_problem import mock_opt_problem
from tradingplatformpoc.trading_platform_utils import get_glpk_solver

logger = logging.getLogger(__name__)


class Test(TestCase):

    solver = get_glpk_solver()
    mod, res = mock_opt_problem(solver)
    agent_guids = ['agent1', 'agent2', 'agent3', 'agent4']
    electricity_pricing = ElectricityPrice(
        elec_wholesale_offset=0.05,
        elec_tax=1.5,
        elec_grid_fee=0.5,
        elec_tax_internal=0,
        elec_grid_fee_internal=0,
        nordpool_data=pd.Series())

    def test_get_power_transfers(self):
        transfers = get_power_transfers(self.mod, datetime.datetime(2024, 2, 1), 'ElecGridAgent', self.agent_guids,
                                        self.electricity_pricing)
        expected_length = len(self.mod.T) * (len(self.mod.I) + 1)  # One for each agent, plus one for external
        self.assertEqual(expected_length, len(transfers))

    def test_get_heat_pump_production(self):
        my_dict = {}
        add_value_per_agent_to_dict(self.mod, datetime.datetime(2024, 2, 1), my_dict, 'Hhp', self.agent_guids)
        self.assertEqual(len(self.mod.I), len(my_dict))
        self.assertEqual(len(self.mod.T), len(list(my_dict.values())[0]))
        self.assertEqual(0, list(list(my_dict.values())[0].values())[0])
