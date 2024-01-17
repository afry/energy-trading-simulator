import logging

import pyomo.environ as pyo
from pyomo.opt import TerminationCondition

logger = logging.getLogger(__name__)


def mock_opt_problem(solver):
    # TODO: DELETE THIS FILE when we start using the optimization solution for real

    # Create a concrete optimization model
    model = pyo.ConcreteModel()

    # Define variables
    model.x = pyo.Var(within=pyo.NonNegativeReals)
    model.y = pyo.Var(within=pyo.NonNegativeReals)

    # Define objective function
    model.obj = pyo.Objective(expr=model.x + 2 * model.y)

    # Define a constraint
    model.con = pyo.Constraint(expr=model.x + 3 * model.y >= 10)

    # Solve the optimization problem
    results = solver.solve(model)

    # Check solver status
    if results.solver.termination_condition == TerminationCondition.optimal:
        logger.info('The solver works.')
        # Access the optimal solution
        logger.info(f'Optimal x: {model.x()}')
        logger.info(f'Optimal y: {model.y()}')
    else:
        logger.error('The solver did not find an optimal solution. Solver status: '
                     + str(results.solver.termination_condition))
