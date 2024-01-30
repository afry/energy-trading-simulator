import logging
from typing import Tuple

import numpy as np

import pandas as pd

import pyomo.environ as pyo
from pyomo.opt import SolverResults, TerminationCondition

logger = logging.getLogger(__name__)


def mock_opt_problem(solver) -> Tuple[pyo.ConcreteModel, SolverResults]:
    # TODO: DELETE THIS FILE (but keep methods below?) when we start using the optimization solution for real

    # Create a concrete optimization model
    model = pyo.ConcreteModel()

    # Sets
    hours_to_run = 6
    n_agents = 4
    model.time = pyo.Set(initialize=range(hours_to_run))  # index of time intervals
    model.agent = pyo.Set(initialize=range(n_agents))  # index of agents
    # Parameters
    model.price_buy = pyo.Param(model.time, initialize=np.random.randn(hours_to_run) + 1)
    model.price_sell = pyo.Param(model.time, initialize=0.9 * (np.ones(hours_to_run) + 1))
    model.power_max_grid = pyo.Param(initialize=500)
    model.power_max_market = pyo.Param(initialize=1000)
    power_dem_df = pd.DataFrame(np.random.randn(n_agents, hours_to_run))
    power_pv_df = pd.DataFrame(np.random.randn(n_agents, hours_to_run))
    model.power_dem = pyo.Param(model.agent, model.time, initialize=lambda m, i, t: power_dem_df.iloc[i, t])
    model.power_pv = pyo.Param(model.agent, model.time, initialize=lambda m, i, t: power_pv_df.iloc[i, t])
    model.Hhpmax = pyo.Param(initialize=70)
    # Define variables
    model.Pbuy_market = pyo.Var(model.time, within=pyo.NonNegativeReals, initialize=0)
    model.Psell_market = pyo.Var(model.time, within=pyo.NonNegativeReals, initialize=0)
    model.U_buy_sell_market = pyo.Var(model.time, within=pyo.Binary, initialize=0)
    model.Pbuy_grid = pyo.Var(model.agent, model.time, within=pyo.NonNegativeReals, initialize=0)
    model.Psell_grid = pyo.Var(model.agent, model.time, within=pyo.NonNegativeReals, initialize=0)
    model.U_power_buy_sell_grid = pyo.Var(model.agent, model.time, within=pyo.Binary, initialize=0)
    model.Hhp = pyo.Var(model.agent, model.time, bounds=(0, model.Hhpmax), within=pyo.NonNegativeReals, initialize=0)
    model.SOCBES = pyo.Var(model.agent, model.time, bounds=(0, 1), within=pyo.NonNegativeReals, initialize=0)

    # Define objective function
    model.obj = pyo.Objective(rule=lambda m, t: sum(m.Pbuy_market[t] * m.price_buy[t]
                                                    - m.Psell_market[t] * m.price_sell[t] for t in m.time))

    # Define a constraint
    model.con1_1 = pyo.Constraint(model.agent, model.time, rule=lambda m, i, t:
                                  m.Pbuy_grid[i, t] <= m.power_max_grid * m.U_power_buy_sell_grid[i, t])
    model.con1_2 = pyo.Constraint(model.agent, model.time, rule=lambda m, i, t:
                                  m.Psell_grid[i, t] <= m.power_max_grid * (1 - m.U_power_buy_sell_grid[i, t]))
    model.con3 = pyo.Constraint(model.time, rule=lambda m, t:
                                m.Pbuy_market[t] <= m.power_max_market * m.U_buy_sell_market[t])
    model.con4 = pyo.Constraint(model.time, rule=lambda m, t:
                                m.Psell_market[t] <= m.power_max_market * (1 - m.U_buy_sell_market[t]))
    # Power balance equation for agents
    model.con5 = pyo.Constraint(model.agent, model.time, rule=lambda m, i, t:
                                m.power_pv[i, t] + m.Pbuy_grid[i, t]
                                == m.power_dem[i, t] + m.Psell_grid[i, t])
    # Power balance equation for grid
    model.con6 = pyo.Constraint(model.time, rule=lambda m, t:
                                sum(m.Psell_grid[i, t] for i in m.agent)
                                + m.Pbuy_market[t] == sum(m.Pbuy_grid[i, t] for i in m.agent)
                                + m.Psell_market[t])

    # Solve the optimization problem
    results = solver.solve(model)

    # Check solver status
    if results.solver.termination_condition == TerminationCondition.optimal:
        logger.info('The solver works.')
        # Access the optimal solution
        logger.info(f'Optimal Pbuy_market: {[i for i in model.Pbuy_market]}')
        logger.info(f'Optimal Psell_market: {[i for i in model.Psell_market]}')
    else:
        logger.error('The solver did not find an optimal solution. Solver status: '
                     + str(results.solver.termination_condition))
    return model, results
