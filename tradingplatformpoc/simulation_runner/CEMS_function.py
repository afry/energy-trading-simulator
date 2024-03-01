from typing import List, Tuple

import pandas as pd

import pyomo.environ as pyo
from pyomo.opt import OptSolver, SolverResults

# This share of high-temp heat need can be covered by low-temp heat (source: BDAB). The rest needs to be covered by
# a booster heat pump.
PERC_OF_HT_COVERABLE_BY_LT = 0.6


def solve_model(solver: OptSolver, summer_mode: bool, n_agents: int, external_elec_buy_price: pd.Series,
                external_elec_sell_price: pd.Series, external_heat_buy_price: float,
                battery_capacity: List[float], battery_charge_rate: List[float], battery_discharge_rate: List[float],
                SOCBES0: List[float], heatpump_COP: List[float], heatpump_max_power: List[float], heatpump_max_heat: List[float],
                booster_heatpump_COP: List[float], booster_heatpump_max_power: List[float], booster_heatpump_max_heat: List[float],
                build_area: List[float], elec_consumption: pd.DataFrame, hot_water_heatdem: pd.DataFrame, space_heating_heatdem: pd.DataFrame,
                cold_consumption: pd.DataFrame, pv_production: pd.DataFrame, battery_efficiency: float = 0.95,
                max_elec_transfer_between_agents: float = 500, max_elec_transfer_to_external: float = 1000,
                max_heat_transfer_between_agents: float = 500, max_heat_transfer_to_external: float = 1000,
                chiller_COP: float = 1.5, thermalstorage_capacity: float = 200, thermalstorage_charge_rate: float = 25,
                thermalstorage_efficiency: float = 0.98, trading_horizon: int = 24) \
        -> Tuple[pyo.ConcreteModel, SolverResults]:
    """
    This function should be exposed to AFRY's trading simulator in some way.
    Which solver to use should be left to the user, so we'll request it as an argument, rather than defining it here.

    Things we'll want to return:
    * The energy flows
    * Whether the solver found a solution
    * Perhaps things like how much heat that was generated from heat pumps
    Perhaps the best way is to do as this is coded at the moment: returning the model object and the solver results
    """
    # Some validation (should probably raise specific exceptions rather than use assert)
    assert len(elec_consumption.index) == n_agents
    assert len(hot_water_heatdem.index) == n_agents
    assert len(space_heating_heatdem.index) == n_agents
    assert len(cold_consumption.index) == n_agents
    assert len(elec_consumption.columns) >= trading_horizon
    assert len(hot_water_heatdem.columns) >= trading_horizon
    assert len(space_heating_heatdem.columns) >= trading_horizon
    assert len(cold_consumption.columns) >= trading_horizon
    assert len(external_elec_buy_price) >= trading_horizon
    assert len(external_elec_sell_price) >= trading_horizon
    assert battery_efficiency >= 0  # Otherwise we'll get division by zero
    assert thermalstorage_efficiency >= 0  # Otherwise we'll get division by zero
    if summer_mode:
        # (1 - PERC_OF_HT_COVERABLE_BY_LT) of the high-temp-heat-demand needs to be covered by the booster heat pump.
        # If the high-temp-heat-demand is higher than this, we won't be able to find a solution (the
        # TerminationCondition will be 'infeasible'). Easier to raise this error straight away, so that the user knows
        # specifically what went wrong.
        max_hot_water_generated = [mhp / (1 - PERC_OF_HT_COVERABLE_BY_LT) for mhp in booster_heatpump_max_heat]
        too_big_hot_water_demand = hot_water_heatdem.gt(max_hot_water_generated, axis=0).any(axis=1)
        if too_big_hot_water_demand.any():
            problematic_agent_indices = [i for i, x in enumerate(too_big_hot_water_demand.tolist()) if x]
            raise RuntimeError('Unfillable hot water demand for agent indices: {}'.format(problematic_agent_indices))

    model = pyo.ConcreteModel()
    # Sets
    model.T = pyo.Set(initialize=range(int(trading_horizon)))  # index of time intervals
    model.I = pyo.Set(initialize=range(int(n_agents)))  # index of agents
    # Parameters
    model.price_buy = pyo.Param(model.T, initialize=external_elec_buy_price)
    model.price_sell = pyo.Param(model.T, initialize=external_elec_sell_price)
    model.Hprice_energy = pyo.Param(initialize=external_heat_buy_price)
    # Grid data
    model.Pmax_grid = pyo.Param(initialize=max_elec_transfer_between_agents)
    model.Hmax_grid = pyo.Param(initialize=max_heat_transfer_between_agents)
    model.Pmax_market = pyo.Param(initialize=max_elec_transfer_to_external)
    model.Hmax_market = pyo.Param(initialize=max_heat_transfer_to_external)
    # Demand data of agents
    model.Pdem = pyo.Param(model.I, model.T, initialize=lambda m, i, t: elec_consumption.iloc[i, t])
    model.Hhw = pyo.Param(model.I, model.T, initialize=lambda m, i, t: hot_water_heatdem.iloc[i, t])
    model.Hsh = pyo.Param(model.I, model.T, initialize=lambda m, i, t: space_heating_heatdem.iloc[i, t])
    model.Cld = pyo.Param(model.I, model.T, initialize=lambda m, i, t: cold_consumption.iloc[i, t])
    model.Ppv = pyo.Param(model.I, model.T, initialize=lambda m, i, t: pv_production.iloc[i, t])
    # BES data
    model.effe = pyo.Param(initialize=battery_efficiency)
    model.SOCBES0 = pyo.Param(model.I, initialize=SOCBES0)
    model.Emax_BES = pyo.Param(model.I, initialize=battery_capacity)
    model.Pmax_BES_Cha = pyo.Param(model.I, initialize=battery_charge_rate)
    model.Pmax_BES_Dis = pyo.Param(model.I, initialize=battery_discharge_rate)
    # Building inertia as thermal energy storage
    model.Energy_shallow_cap = pyo.Param(model.I, initialize=lambda model, i: 0.046 * build_area[i])
    model.Energy_deep_cap = pyo.Param(model.I, initialize=lambda model, i: 0.291 * build_area[i])
    model.Heat_rate_shallow = pyo.Param(model.I, initialize=lambda model, i: 0.023 * build_area[i])
    model.Kval = pyo.Param(model.I, initialize=lambda model, i: 0.03 * build_area[i])
    model.Kloss_shallow = pyo.Param(model.I, initialize=lambda model, i: 0.9913)
    model.Kloss_deep = pyo.Param(model.I, initialize=lambda model, i: 0.9963)
    # Heat pump data
    model.COPhp = pyo.Param(model.I, initialize=heatpump_COP)
    model.Phpmax = pyo.Param(model.I, initialize=heatpump_max_power)
    model.Hhpmax = pyo.Param(model.I, initialize=heatpump_max_heat)
    # Booster heat pump data
    model.COPhpB = pyo.Param(model.I, initialize=booster_heatpump_COP)
    model.PhpBmax = pyo.Param(model.I, initialize=booster_heatpump_max_power)
    model.HhpBmax = pyo.Param(model.I, initialize=booster_heatpump_max_heat)
    # Chiller data
    model.COPcc = pyo.Param(initialize=chiller_COP)
    # Thermal energy storage data
    model.efft = pyo.Param(initialize=thermalstorage_efficiency)
    model.Emax_TES = pyo.Param(initialize=thermalstorage_capacity)
    model.Hmax_TES = pyo.Param(initialize=thermalstorage_charge_rate)

    # Variable
    model.Pbuy_market = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Psell_market = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.U_buy_sell_market = pyo.Var(model.T, within=pyo.Binary, initialize=0)
    model.Hbuy_market = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Pbuy_grid = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Psell_grid = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.U_power_buy_sell_grid = pyo.Var(model.I, model.T, within=pyo.Binary, initialize=0)
    model.Hbuy_grid = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hsell_grid = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.U_heat_buy_sell_grid = pyo.Var(model.I, model.T, within=pyo.Binary, initialize=0)
    model.Pcha = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Pdis = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.SOCBES = pyo.Var(model.I, model.T, bounds=(0, 1), within=pyo.NonNegativeReals,
                           initialize=lambda m, i, t: SOCBES0[i])
    model.Hhp = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Php = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hcha = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hdis = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.SOCTES = pyo.Var(model.T, bounds=(0, 1), within=pyo.NonNegativeReals, initialize=1)
    model.Ccc = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hcc = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Pcc = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Energy_shallow = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hcha_shallow = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hdis_shallow = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Flow = pyo.Var(model.I, model.T, within=pyo.Reals, initialize=0)
    model.Loss_shallow = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Energy_deep = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Loss_deep = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    if summer_mode:
        model.HhpB = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
        model.PhpB = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)

    add_obj_and_constraints(model, summer_mode)

    # Solve!
    results = solver.solve(model)
    return model, results


def add_obj_and_constraints(model: pyo.ConcreteModel, summer_mode: bool):
    # Objective function:
    model.obj = pyo.Objective(rule=obj_rul, sense=pyo.minimize)
    model.con1_1 = pyo.Constraint(model.I, model.T, rule=con_rul1_1)
    model.con1_2 = pyo.Constraint(model.I, model.T, rule=con_rul1_2)
    model.con2_1 = pyo.Constraint(model.I, model.T, rule=con_rul2_1)
    model.con3 = pyo.Constraint(model.T, rule=con_rul3)
    model.con4 = pyo.Constraint(model.T, rule=con_rul4)
    if summer_mode:
        model.con2_2_2 = pyo.Constraint(model.I, model.T, rule=con_rul2_2_2)
        model.con5_1_2 = pyo.Constraint(model.I, model.T, rule=con_rul5_1_2)
        model.con5_2_1 = pyo.Constraint(model.I, model.T, rule=con_rul5_2_1)
        model.con5_2_2 = pyo.Constraint(model.I, model.T, rule=con_rul5_2_2)
    else:
        model.con2_2_1 = pyo.Constraint(model.I, model.T, rule=con_rul2_2_1)
        model.con5_1_1 = pyo.Constraint(model.I, model.T, rule=con_rul5_1_1)
        model.con5_2 = pyo.Constraint(model.I, model.T, rule=con_rul5_2)
    model.con5_3 = pyo.Constraint(model.I, model.T, rule=con_rul5_3)
    model.con5_4 = pyo.Constraint(model.I, model.T, rule=con_rul5_4)
    model.con5_5 = pyo.Constraint(model.I, model.T, rule=con_rul5_5)
    model.con5_6 = pyo.Constraint(model.I, model.T, rule=con_rul5_6)
    model.con5_7 = pyo.Constraint(model.I, model.T, rule=con_rul5_7)
    model.con5_8 = pyo.Constraint(model.I, model.T, rule=con_rul5_8)
    model.con5_9 = pyo.Constraint(model.I, model.T, rule=con_rul5_9)
    model.con5_10 = pyo.Constraint(model.I, model.T, rule=con_rul5_10)
    model.con5_11 = pyo.Constraint(model.I, model.T, rule=con_rul5_11)
    model.con6_1 = pyo.Constraint(model.T, rule=con_rul6_1)
    model.con6_2 = pyo.Constraint(model.T, rule=con_rul6_2)
    model.con6_3 = pyo.Constraint(model.T, rule=con_rul6_3)
    model.con7 = pyo.Constraint(model.I, model.T, rule=con_rul7)
    model.con8 = pyo.Constraint(model.I, model.T, rule=con_rul8)
    model.con9 = pyo.Constraint(model.I, model.T, rule=con_rul9)
    model.con10 = pyo.Constraint(model.I, rule=con_rul10)
    model.con10_1 = pyo.Constraint(model.I, model.T, rule=con_rul10_1)
    model.con11 = pyo.Constraint(model.I, model.T, rule=con_rul11)
    model.con11_1 = pyo.Constraint(model.I, model.T, rule=con_rul11_1)
    model.con11_2 = pyo.Constraint(model.I, model.T, rule=con_rul11_2)
    if summer_mode:
        model.con11_3 = pyo.Constraint(model.I, model.T, rule=con_rul11_3)
        model.con11_4 = pyo.Constraint(model.I, model.T, rule=con_rul11_4)
        model.con17_1 = pyo.Constraint(model.T, rule=con_rul17_1)
    else:
        model.con17_2 = pyo.Constraint(model.T, rule=con_rul17_2)
    model.con12 = pyo.Constraint(model.T, rule=con_rul12)
    model.con13 = pyo.Constraint(model.T, rule=con_rul13)
    model.con14 = pyo.Constraint(model.T, rule=con_rul14)
    model.con15 = pyo.Constraint(rule=con_rul15)
    model.con15_1 = pyo.Constraint(model.T, rule=con_rul15_1)
    model.con16 = pyo.Constraint(model.T, rule=con_rul16)


# Objective function: minimize the total charging cost (eq. 1 of the report)
def obj_rul(model):
    return sum(
        model.Pbuy_market[t] * model.price_buy[t] - model.Psell_market[t] * model.price_sell[t]
        + model.Hbuy_market[t] * model.Hprice_energy
        for t in model.T)


# Constraints:
# Buying and selling heat/electricity from agents cannot happen at the same time
# and should be restricted to its maximum value (Pmax_grid) (eqs. 10 to 15 of the report)
def con_rul1_1(model, i, t):
    return model.Pbuy_grid[i, t] <= model.Pmax_grid * model.U_power_buy_sell_grid[i, t]


def con_rul1_2(model, i, t):
    return model.Hbuy_grid[i, t] <= model.Hmax_grid * model.U_heat_buy_sell_grid[i, t]


def con_rul2_1(model, i, t):
    return model.Psell_grid[i, t] <= model.Pmax_grid * (1 - model.U_power_buy_sell_grid[i, t])


def con_rul2_2_1(model, i, t):
    # Only used in winter mode : Due to high temperature of district heating (60 deg. C),
    # it is not possible to export heat from building to the district heating
    return model.Hsell_grid[i, t] <= 0


def con_rul2_2_2(model, i, t):
    # Only used in summer mode
    return model.Hsell_grid[i, t] <= model.Hmax_grid * (1 - model.U_heat_buy_sell_grid[i, t])


# Buying and selling power from the market cannot happen at the same time
# and should be restricted to its maximum value (Pmax_market) (eqs. 2 and 4 of the report)
def con_rul3(model, t):
    return model.Pbuy_market[t] <= model.Pmax_market * model.U_buy_sell_market[t]


def con_rul4(model, t):
    return model.Psell_market[t] <= model.Pmax_market * (1 - model.U_buy_sell_market[t])


# (eq. 2 and 3 of the report)
# Electrical/heat/cool power balance equation for agents
def con_rul5_1_1(model, i, t):
    # Only used in winter mode
    return model.Ppv[i, t] + model.Pdis[i, t] + model.Pbuy_grid[i, t] == \
        model.Pdem[i, t] + model.Php[i, t] + model.Pcha[i, t] + model.Psell_grid[i, t]


def con_rul5_1_2(model, i, t):
    # Only used in summer mode
    return model.Ppv[i, t] + model.Pdis[i, t] + model.Pbuy_grid[i, t] == \
        model.Pdem[i, t] + model.Php[i, t] + model.PhpB[i, t] + model.Pcha[i, t] + model.Psell_grid[i, t]


def con_rul5_2(model, i, t):
    # Only used in winter mode
    return model.Hbuy_grid[i, t] + model.Hhp[i, t] + model.Hdis_shallow[i, t] == \
           model.Hsell_grid[i, t] + model.Hcha_shallow[i, t] + model.Hhw[i, t] + model.Hsh[i, t]


def con_rul5_2_1(model, i, t):
    # Only used in summer mode
    return model.Hbuy_grid[i, t] + model.Hhp[i, t] + model.Hdis_shallow[i, t] == \
        model.Hsell_grid[i, t] + model.Hcha_shallow[i, t] + PERC_OF_HT_COVERABLE_BY_LT * model.Hhw[i, t] + \
        model.Hsh[i, t]


# (eq. 5 and 6 of the report)
def con_rul5_2_2(model, i, t):
    # Only used in summer mode
    return model.HhpB[i, t] == (1 - PERC_OF_HT_COVERABLE_BY_LT) * model.Hhw[i, t]


# (eqs. 22 to 28 of the report)
def con_rul5_3(model, i, t):
    if t == 0:
        return model.Energy_shallow[i, 0] == 0 + model.Hcha_shallow[i, 0] \
            - model.Hdis_shallow[i, 0] - model.Flow[i, 0] - model.Loss_shallow[i, 0]
    else:
        return model.Energy_shallow[i, t] == model.Energy_shallow[i, t - 1] + model.Hcha_shallow[i, t] \
            - model.Hdis_shallow[i, t] - model.Flow[i, t] - model.Loss_shallow[i, t]


def con_rul5_4(model, i, t):
    return model.Hdis_shallow[i, t] <= model.Heat_rate_shallow[i]


def con_rul5_5(model, i, t):
    return model.Hcha_shallow[i, t] <= model.Heat_rate_shallow[i]


def con_rul5_6(model, i, t):
    if t == 0:
        return model.Energy_deep[i, 0] == 0 + model.Flow[i, 0] - model.Loss_deep[i, 0]
    else:
        return model.Energy_deep[i, t] == model.Energy_deep[i, t - 1] + model.Flow[i, t] - model.Loss_deep[i, t]


def con_rul5_7(model, i, t):
    if (model.Energy_shallow_cap[i] == 0) or (model.Energy_deep_cap[i] == 0):
        return model.Flow[i, t] == 0
    return model.Flow[i, t] == ((model.Energy_shallow[i, t] / model.Energy_shallow_cap[i])
                                - (model.Energy_deep[i, t] / model.Energy_deep_cap[i])) * model.Kval[i]


def con_rul5_8(model, i, t):
    if t == 0:
        return model.Loss_shallow[i, 0] == 0
    else:
        return model.Loss_shallow[i, t] == model.Energy_shallow[i, t - 1] * (1 - model.Kloss_shallow[i])


def con_rul5_9(model, i, t):
    if t == 0:
        return model.Loss_deep[i, 0] == 0
    else:
        return model.Loss_deep[i, t] == model.Energy_deep[i, t - 1] * (1 - model.Kloss_deep[i])


def con_rul5_10(model, i, t):
    return model.Hdis_shallow[i, t] <= model.Hsh[i, t]


def con_rul5_11(model, i, t):
    return model.Hcha_shallow[i, t] <= model.Hhpmax[i] + model.Hmax_grid - model.Hsh[i, t]


# Electrical/heat/cool power balance equation for grid (eqs. 7 to 9 of the report)
def con_rul6_1(model, t):
    return sum(model.Psell_grid[i, t] for i in model.I) + model.Pbuy_market[t] == \
        sum(model.Pbuy_grid[i, t] for i in model.I) + model.Psell_market[t] + model.Pcc[t]


def con_rul6_2(model, t):
    return sum(model.Hsell_grid[i, t] for i in model.I) + model.Hbuy_market[t] + \
        model.Hdis[t] + model.Hcc[t] == sum(model.Hbuy_grid[i, t] for i in model.I) + model.Hcha[t]


def con_rul6_3(model, t):
    return model.Ccc[t] == sum(model.Cld[i, t] for i in model.I)


# Battery energy storage model (eqs. 16 to 19 of the report)
# Maximum charging/discharging power limitations
def con_rul7(model, i, t):
    return model.Pdis[i, t] <= model.Pmax_BES_Dis[i]


def con_rul8(model, i, t):
    return model.Pcha[i, t] <= model.Pmax_BES_Cha[i]


# State of charge modelling
def con_rul9(model, i, t):
    if model.Emax_BES[i] == 0:
        # No storage capacity, then we need to ensure that charge and discharge are 0 as well.
        return model.Pcha[i, t] + model.Pdis[i, t] == model.Emax_BES[i]
    # We assume that model.effe cannot be 0
    if t == 0:
        charge = model.Pcha[i, 0] * model.effe / model.Emax_BES[i]
        discharge = model.Pdis[i, 0] / (model.Emax_BES[i] * model.effe)
        return model.SOCBES[i, 0] == model.SOCBES0[i] + charge - discharge
    else:
        charge = model.Pcha[i, t] * model.effe / model.Emax_BES[i]
        discharge = model.Pdis[i, t] / (model.Emax_BES[i] * model.effe)
        return model.SOCBES[i, t] == model.SOCBES[i, t - 1] + charge - discharge


def con_rul10(model, i):
    return model.SOCBES[i, len(model.T)-1] == model.SOCBES0[i]


def con_rul10_1(model, i, t):
    return model.Pdis[i, t] / model.Pmax_BES_Dis[i] + model.Pcha[i, t] / model.Pmax_BES_Cha[i] <= 1


# Heat pump model (eq. 20 of the report)
def con_rul11(model, i, t):
    return model.Hhp[i, t] == model.COPhp[i] * model.Php[i, t]


def con_rul11_1(model, i, t):
    return model.Hhp[i, t] <= model.Hhpmax[i]


def con_rul11_2(model, i, t):
    return model.Php[i, t] <= model.Phpmax[i]


def con_rul11_3(model, i, t):
    # Only used in summer mode
    return model.HhpB[i, t] <= model.HhpBmax[i]


def con_rul11_4(model, i, t):
    # Only used in summer mode
    return model.HhpB[i, t] == model.COPhpB[i] * model.PhpB[i, t]


# Thermal energy storage model (eqs. 32 to 25 of the report)
# Maximum charging/discharging heat power limitations
def con_rul12(model, t):
    return model.Hdis[t] <= model.Hmax_TES


def con_rul13(model, t):
    return model.Hcha[t] <= model.Hmax_TES


# State of charge modelling
def con_rul14(model, t):
    if model.Emax_TES == 0:
        # No storage capacity, then we need to ensure that charge and discharge are 0 as well.
        return model.Hdis[t] + model.Hcha[t] == model.Emax_TES
    # We assume that model.efft cannot be 0
    if t == 0:
        discharge = model.Hdis[0] / (model.Emax_TES * model.efft)
        charge = model.Hcha[0] * model.efft / model.Emax_TES
        return model.SOCTES[0] == 1 + charge - discharge
    else:
        discharge = model.Hdis[t] / (model.Emax_TES * model.efft)
        charge = model.Hcha[t] * model.efft / model.Emax_TES
        return model.SOCTES[t] == model.SOCTES[t - 1] + charge - discharge


def con_rul15(model):
    return model.SOCTES[len(model.T)-1] == 1


def con_rul15_1(model, t):
    return model.Hdis[t] / model.Hmax_TES + model.Hcha[t] / model.Hmax_TES <= 1


# Compression chiller model (eqs. 29 to 31 of the report)
def con_rul16(model, t):
    return model.Ccc[t] == model.COPcc * model.Pcc[t]


def con_rul17_1(model, t):
    # Only used in summer mode
    return model.Hcc[t] <= (1+model.COPcc) * model.Pcc[t]


def con_rul17_2(model, t):
    # Only used in winter mode : Due to high temperature of district heating (60 deg. C),
    # it is not possible to export heat from building to the district heating
    return model.Hcc[t] <= 0
