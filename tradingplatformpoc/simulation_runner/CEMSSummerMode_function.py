from typing import List, Tuple

import pandas as pd

import pyomo.environ as pyo
from pyomo.opt import OptSolver, SolverResults


def solve_model(solver: OptSolver, n_agents: int, external_elec_buy_price: pd.Series,
                external_elec_sell_price: pd.Series, external_heat_buy_price: List[float],
                battery_capacity: List[float], battery_charge_rate: List[float], battery_discharge_rate: List[float],
                SOCBES0: List[float], heatpump_COP: List[float], heatpump_max_power: List[float],
                heatpump_max_heat: List[float],
                energy_shallow_cap: List[float], energy_deep_cap: List[float], heat_rate_shallow: List[float],
                Kval: List[float], Kloss_shallow: List[float], Kloss_deep: List[float],
                elec_consumption: pd.DataFrame, hot_water_heatdem: pd.DataFrame, space_heating_heatdem: pd.DataFrame,
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
    assert len(external_heat_buy_price) >= 12

    model = pyo.ConcreteModel()
    # Sets
    model.T = pyo.Set(initialize=range(int(trading_horizon)))  # index of time intervals
    model.I = pyo.Set(initialize=range(int(n_agents)))  # index of agents
    model.M = pyo.Set(initialize=range(12))  # index of months
    # Parameters
    model.price_buy = pyo.Param(model.T, initialize=external_elec_buy_price)
    model.price_sell = pyo.Param(model.T, initialize=external_elec_sell_price)
    model.Hprice_energy = pyo.Param(model.M, initialize=external_heat_buy_price)
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
    model.Energy_shallow_cap = pyo.Param(model.I, initialize=energy_shallow_cap)
    model.Energy_deep_cap = pyo.Param(model.I, initialize=energy_deep_cap)
    model.Heat_rate_shallow = pyo.Param(model.I, initialize=heat_rate_shallow)
    model.Kval = pyo.Param(model.I, initialize=Kval)
    model.Kloss_shallow = pyo.Param(model.I, initialize=Kloss_shallow)
    model.Kloss_deep = pyo.Param(model.I, initialize=Kloss_deep)
    # Heat pump data
    model.COPhp = pyo.Param(model.I, initialize=heatpump_COP)
    model.Phpmax = pyo.Param(model.I, initialize=heatpump_max_power)
    model.Hhpmax = pyo.Param(model.I, initialize=heatpump_max_heat)
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
    model.SOCBES = pyo.Var(model.I, model.T, bounds=(0, 1), within=pyo.NonNegativeReals, initialize=0)
    model.Hhp = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hhp1 = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hhp2 = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Php = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hcha = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hdis = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.SOCTES = pyo.Var(model.T, bounds=(0, 1), within=pyo.NonNegativeReals, initialize=0)
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

    add_obj_and_constraints(model)

    # Solve!
    results = solver.solve(model)
    return model, results


def add_obj_and_constraints(model: pyo.ConcreteModel):
    # Objective function:
    model.obj = pyo.Objective(rule=obj_rul, sense=pyo.minimize)
    # Constraints - would be nice if the constraint rules could be named in a more explanatory way
    model.con1_1 = pyo.Constraint(model.I, model.T, rule=con_rul1_1)
    model.con1_2 = pyo.Constraint(model.I, model.T, rule=con_rul1_2)
    model.con2_1 = pyo.Constraint(model.I, model.T, rule=con_rul2_1)
    model.con2_2 = pyo.Constraint(model.I, model.T, rule=con_rul2_2)
    model.con3 = pyo.Constraint(model.T, rule=con_rul3)
    model.con4 = pyo.Constraint(model.T, rule=con_rul4)
    model.con5_1 = pyo.Constraint(model.I, model.T, rule=con_rul5_1)
    model.con5_2_1 = pyo.Constraint(model.I, model.T, rule=con_rul5_2_1)
    model.con5_2_2 = pyo.Constraint(model.I, model.T, rule=con_rul5_2_2)
    model.con5_2_3 = pyo.Constraint(model.I, model.T, rule=con_rul5_2_3)
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
    model.con11_3 = pyo.Constraint(model.I, model.T, rule=con_rul11_3)
    model.con11_4 = pyo.Constraint(model.I, model.T, rule=con_rul11_4)
    model.con12 = pyo.Constraint(model.T, rule=con_rul12)
    model.con13 = pyo.Constraint(model.T, rule=con_rul13)
    model.con14 = pyo.Constraint(model.T, rule=con_rul14)
    model.con15 = pyo.Constraint(rule=con_rul15)
    model.con15_1 = pyo.Constraint(model.T, rule=con_rul15_1)
    model.con16 = pyo.Constraint(model.T, rule=con_rul16)
    model.con17 = pyo.Constraint(model.T, rule=con_rul17)


# Objective function: minimize the total charging cost (eq. 1 of the report)
def obj_rul(model):
    return sum(
        model.Pbuy_market[t] * model.price_buy[t] - model.Psell_market[t] * model.price_sell[t]
        + model.Hbuy_market[t] * model.Hprice_energy[0]
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


def con_rul2_2(model, i, t):
    return model.Hsell_grid[i, t] <= model.Hmax_grid * (1 - model.U_heat_buy_sell_grid[i, t])


# Buying and selling power from the market cannot happen at the same time
# and should be restricted to its maximum value (Pmax_market)
def con_rul3(model, t):
    return model.Pbuy_market[t] <= model.Pmax_market * model.U_buy_sell_market[t]


def con_rul4(model, t):
    return model.Psell_market[t] <= model.Pmax_market * (1 - model.U_buy_sell_market[t])


# Electrical/heat/cool power balance equation for agents (eqs. 2 and 4 of the report)
def con_rul5_1(model, i, t):
    return model.Ppv[i, t] + model.Pdis[i, t] + model.Pbuy_grid[i, t] == \
        model.Pdem[i, t] + model.Php[i, t] + model.Pcha[i, t] + model.Psell_grid[i, t]


def con_rul5_2_1(model, i, t):
    return model.Hbuy_grid[i, t] + model.Hhp1[i, t] + model.Hdis_shallow[i, t] == \
        model.Hsell_grid[i, t] + model.Hcha_shallow[i, t] + 0.6 * model.Hhw[i, t] + model.Hsh[i, t]


# (eq. 5 and 6 of the report)
def con_rul5_2_2(model, i, t):
    return model.Hhp2[i, t] == 0.4 * model.Hhw[i, t]


def con_rul5_2_3(model, i, t):
    return model.Hhp[i, t] == model.Hhp1[i, t] + model.Hhp2[i, t]


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
    return model.Flow[i, t] == ((model.Energy_shallow[i, t] / model.Energy_shallow_cap[i])
                                - (model.Energy_deep[i, t] / model.Energy_deep_cap[i])) * model.Kval[i]


def con_rul5_8(model, i, t):
    return model.Loss_shallow[i, t] == model.Energy_shallow[i, t] * (1 - model.Kloss_shallow[i])


def con_rul5_9(model, i, t):
    return model.Loss_deep[i, t] == model.Energy_deep[i, t] * (1 - model.Kloss_deep[i])


def con_rul5_10(model, i, t):
    return model.Hdis_shallow[i, t] <= model.Hsh.iloc[i, t]


def con_rul5_11(model, i, t):
    return model.Hcha_shallow[i, t] <= model.Hhpmax[i] + model.Hmax_grid - model.Hsh.iloc[i, t]


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
    if t == 0:
        return model.SOCBES[i, 0] == model.SOCBES0[i] + model.Pcha[i, 0] * model.effe / model.Emax_BES[i] - model.Pdis[i, 0] / (
                    model.Emax_BES[i] * model.effe)
    else:
        return model.SOCBES[i, t] == model.SOCBES[i, t - 1] + model.Pcha[i, t] * model.effe / model.Emax_BES[i] - \
            model.Pdis[i, t] / (
                    model.Emax_BES[i] * model.effe)


def con_rul10(model, i):
    return model.SOCBES[i, len(model.T)-1] == model.SOCBES0[i]


def con_rul10_1(model, i, t):
    return model.Pdis[i, t]/model.Pmax_BES_Dis[i] + model.Pcha[i, t]/model.Pmax_BES_Cha[i] <= 1


# Heat pump model (eq. 20 of the report)
def con_rul11(model, i, t):
    return model.Hhp[i, t] == model.COPhp[i] * model.Php[i, t]


def con_rul11_1(model, i, t):
    return model.Hhp[i, t] <= model.Hhpmax[i]


def con_rul11_2(model, i, t):
    return model.Php[i, t] <= model.Phpmax[i]


def con_rul11_3(model, i, t):
    return model.Hhp1[i, t] <= model.Hhpmax[i]


def con_rul11_4(model, i, t):
    return model.Hhp2[i, t] <= model.Hhpmax[i]


# Thermal energy storage model (eqs. 32 to 25 of the report)
# Maximum charging/discharging heat power limitations
def con_rul12(model, t):
    return model.Hdis[t] <= model.Hmax_TES


def con_rul13(model, t):
    return model.Hcha[t] <= model.Hmax_TES


# State of charge modelling
def con_rul14(model, t):
    if t == 0:
        return model.SOCTES[0] == 1 + model.Hcha[0] * model.efft / model.Emax_TES - model.Hdis[0] / (
                    model.Emax_TES * model.efft)
    else:
        return model.SOCTES[t] == model.SOCTES[t - 1] + model.Hcha[t] * model.efft / model.Emax_TES - model.Hdis[t] / (
                model.Emax_TES * model.efft)


def con_rul15(model):
    return model.SOCTES[len(model.T)-1] == 1


def con_rul15_1(model, t):
    return model.Hdis[t]/model.Hmax_TES + model.Hcha[t]/model.Hmax_TES <= 1


# Compression chiller model (eqs. 29 to 31 of the report)
def con_rul16(model, t):
    return model.Ccc[t] == model.COPcc * model.Pcc[t]


def con_rul17(model, t):
    return model.Hcc[t] <= (1+model.COPcc) * model.Pcc[t]
