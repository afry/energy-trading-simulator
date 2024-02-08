import datetime
import logging
import platform
from unittest import TestCase

import pyomo.environ as pyo

from tradingplatformpoc.settings import settings
from tradingplatformpoc.simulation_runner.chalmers_interface import add_value_per_agent_to_dict, \
    get_power_transfers
from tradingplatformpoc.simulation_runner.optimization_problem import mock_opt_problem


logger = logging.getLogger(__name__)


class Test(TestCase):

    if platform.system() == 'Linux':
        logger.info('Linux system')
        solver = pyo.SolverFactory('glpk')
    else:
        logger.info('Not a linux system, using GLPK_PATH')
        solver = pyo.SolverFactory('glpk', executable=settings.GLPK_PATH)

    def test_get_power_transfers(self):
        mod, res = mock_opt_problem(self.solver)
        transfers = get_power_transfers(mod, datetime.datetime(2024, 2, 1))
        expected_length = len(mod.time) * (len(mod.agent) + 1)  # One for each agent, plus one for external
        self.assertEqual(expected_length, len(transfers))

    def test_get_heat_pump_production(self):
        mod, res = mock_opt_problem(self.solver)
        my_dict = {}
        add_value_per_agent_to_dict(mod, datetime.datetime(2024, 2, 1), my_dict, 'Hhp')
        self.assertEqual(len(mod.agent), len(my_dict))
        self.assertEqual(len(mod.time), len(list(my_dict.values())[0]))
        self.assertEqual(0, list(list(my_dict.values())[0].values())[0])
