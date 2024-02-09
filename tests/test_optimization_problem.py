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

    mod, res = mock_opt_problem(solver)
    agent_guids = ['agent1', 'agent2', 'agent3', 'agent4']

    def test_get_power_transfers(self):
        transfers = get_power_transfers(self.mod, datetime.datetime(2024, 2, 1), 'ElecGridAgent', self.agent_guids)
        expected_length = len(self.mod.time) * (len(self.mod.agent) + 1)  # One for each agent, plus one for external
        self.assertEqual(expected_length, len(transfers))

    def test_get_heat_pump_production(self):
        my_dict = {}
        add_value_per_agent_to_dict(self.mod, datetime.datetime(2024, 2, 1), my_dict, 'Hhp', self.agent_guids)
        self.assertEqual(len(self.mod.agent), len(my_dict))
        self.assertEqual(len(self.mod.time), len(list(my_dict.values())[0]))
        self.assertEqual(0, list(list(my_dict.values())[0].values())[0])
