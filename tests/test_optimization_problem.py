import datetime
import platform
from unittest import TestCase

import pyomo.environ as pyo

from tradingplatformpoc.settings import settings
from tradingplatformpoc.simulation_runner.optimization_problem import get_power_transfers, mock_opt_problem


class Test(TestCase):

    if platform.system() == 'Linux':
        solver = pyo.SolverFactory('glpk')
    else:
        solver = pyo.SolverFactory('glpk', executable=settings.GLPK_PATH)

    def test_mock_opt_problem(self):
        mod, res = mock_opt_problem(self.solver)
        transfers = get_power_transfers(mod, datetime.datetime(2024, 2, 1))
        print(len(transfers))
