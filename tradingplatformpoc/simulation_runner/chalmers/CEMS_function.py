from typing import List, Tuple

import numpy as np

import pandas as pd

import pyomo.environ as pyo
from pyomo.opt import OptSolver, SolverResults

from tradingplatformpoc.simulation_runner.chalmers.domain import CEMSError, PERC_OF_HT_COVERABLE_BY_LT


def solve_model(solver: OptSolver, summer_mode: bool, month: int, n_agents: int, nordpool_price: pd.Series,
                external_heat_buy_price: float,
                battery_capacity: List[float], battery_charge_rate: List[float], battery_discharge_rate: List[float],
                SOCBES0: List[float], HP_Cproduct_active: list[bool], heatpump_COP: List[float],
                heatpump_max_power: List[float], heatpump_max_heat: List[float],
                booster_heatpump_COP: List[float], booster_heatpump_max_power: List[float],
                booster_heatpump_max_heat: List[float], build_area: List[float], SOCTES0: List[float],
                thermalstorage_max_temp: List[float], thermalstorage_volume: List[float], BITES_Eshallow0: List[float],
                BITES_Edeep0: List[float], borehole: List[bool],
                elec_consumption: pd.DataFrame, hot_water_heatdem: pd.DataFrame, space_heating_heatdem: pd.DataFrame,
                cold_consumption: pd.DataFrame, pv_production: pd.DataFrame,
                excess_low_temp_heat: pd.DataFrame, excess_high_temp_heat: pd.DataFrame,
                elec_trans_fee: float, elec_tax_fee: float, incentive_fee: float,
                hist_top_three_elec_peak_load: list, elec_peak_load_fee: float,
                hist_monthly_heat_peak_energy: float, heat_peak_load_fee: float,
                battery_efficiency: float = 0.95,
                max_elec_transfer_between_agents: float = 500, max_elec_transfer_to_external: float = 1000,
                max_heat_transfer_between_agents: float = 500, max_heat_transfer_to_external: float = 1000,
                chiller_COP: float = 1.5, chiller_heat_recovery: bool = True, Pccmax: float = 100,
                thermalstorage_efficiency: float = 0.98,
                heat_trans_loss: float = 0.05, cold_trans_loss: float = 0.05, trading_horizon: int = 24) \
        -> Tuple[pyo.ConcreteModel, SolverResults]:
    """
    This function should be exposed to AFRY's trading simulator in some way.
    Which solver to use should be left to the user, so we'll request it as an argument, rather than defining it here.
    """
    # Some validation (should probably raise specific exceptions rather than use assert)
    assert len(elec_consumption.index) == n_agents
    assert len(hot_water_heatdem.index) == n_agents
    assert len(space_heating_heatdem.index) == n_agents
    assert len(cold_consumption.index) == n_agents
    assert len(pv_production.index) == n_agents
    assert len(excess_low_temp_heat.index) == n_agents
    assert len(excess_high_temp_heat.index) == n_agents
    assert len(elec_consumption.columns) >= trading_horizon
    assert len(hot_water_heatdem.columns) >= trading_horizon
    assert len(space_heating_heatdem.columns) >= trading_horizon
    assert len(cold_consumption.columns) >= trading_horizon
    assert len(pv_production.columns) >= trading_horizon
    assert len(excess_low_temp_heat.columns) >= trading_horizon
    assert len(excess_high_temp_heat.columns) >= trading_horizon
    assert len(nordpool_price) >= trading_horizon
    assert battery_efficiency > 0  # Otherwise we'll get division by zero
    assert thermalstorage_efficiency > 0  # Otherwise we'll get division by zero
    assert heat_trans_loss > 0  # Otherwise we may get simultaneous buying and selling of heat

    # Energy per degree C in each agent's tank
    # Specific heat of Water is 4182 J/(kg C)
    # Density of water is 998 kg/m3
    # This assumes that HTESdis and HTEScha are in kW. If they are in watt,
    # 1000 should be removed from the following formulation:
    kwh_per_deg = [v * 4182 * 998 / 3600000 for v in thermalstorage_volume]

    # When running in summer mode, agents cannot buy high-temperature district heating, so all hot water needs to be
    # covered, to (1 - PERC_OF_HT_COVERABLE_BY_LT) * 100%, by the booster heat pump, but agents can also use the
    # accumulator tank.
    # (Hhw - acc_tank_capacity) * (1 - PERC_OF_HT_COVERABLE_BY_LT) must be covered by booster in any given hour.
    # If the booster cannot cover this, we won't be able to find a solution (the TerminationCondition will be
    # 'infeasible'). Easier to raise this error straight away, so that the user knows specifically what went wrong.
    if summer_mode:
        max_tank_dis = [x * y for x, y in zip(kwh_per_deg, thermalstorage_max_temp)]
        must_be_covered_by_booster = hot_water_heatdem.sub(max_tank_dis, axis=0) * (1 - PERC_OF_HT_COVERABLE_BY_LT)
        too_big_hot_water_demand = must_be_covered_by_booster.gt(booster_heatpump_max_heat, axis=0).any(axis=1)
        if sum(too_big_hot_water_demand) > 0:
            problematic_agent_indices = [i for i, x in enumerate(too_big_hot_water_demand) if x]
            raise CEMSError(message='Unfillable hot water demand for agent(s)',
                            agent_indices=problematic_agent_indices,
                            hour_indices=[])

    # Similarly, check the maximum cooling produced vs the cooling demand
    max_cooling_produced_for_1_hour = Pccmax * chiller_COP \
                                      + sum([(hp_cop - 1) * max_php if hpc_active else
                                             np.inf if has_bh and month not in [6, 7, 8] else 0
                                             for hp_cop, max_php, hpc_active, has_bh in
                                             zip(heatpump_COP, heatpump_max_power, HP_Cproduct_active, borehole)])
    too_big_cool_demand = cold_consumption.sum(axis=0).gt(max_cooling_produced_for_1_hour)
    if too_big_cool_demand.any():
        problematic_hours = [i for i, x in enumerate(too_big_cool_demand) if x]
        raise CEMSError(message='Unfillable cooling demand in LEC',
                        agent_indices=[],
                        hour_indices=problematic_hours)

    model = pyo.ConcreteModel(name="LEC")
    # Sets
    model.T = pyo.Set(initialize=range(int(trading_horizon)))  # index of time intervals
    model.I = pyo.Set(initialize=range(int(n_agents)))  # index of agents
    # Parameters
    model.penalty = pyo.Param(initialize=1000)
    model.nordpool_price = pyo.Param(model.T, initialize=nordpool_price)
    model.elec_peak_load_fee = pyo.Param(initialize=elec_peak_load_fee)
    model.elec_trans_fee = pyo.Param(initialize=elec_trans_fee)
    model.elec_tax_fee = pyo.Param(initialize=elec_tax_fee)
    model.incentive_fee = pyo.Param(initialize=incentive_fee)
    model.Hprice_energy = pyo.Param(initialize=external_heat_buy_price)
    model.heat_peak_load_fee = pyo.Param(initialize=heat_peak_load_fee)
    # Grid data
    model.Pmax_grid = pyo.Param(initialize=max_elec_transfer_between_agents)
    model.Hmax_grid = pyo.Param(initialize=max_heat_transfer_between_agents)
    model.Pmax_market = pyo.Param(initialize=max_elec_transfer_to_external)
    model.Hmax_market = pyo.Param(initialize=max_heat_transfer_to_external)
    model.hist_top_three_elec_peak_load = pyo.Param(range(3), initialize={i: hist_top_three_elec_peak_load[i]
                                                                          for i in range(3)})
    model.Hist_monthly_heat_peak_energy = pyo.Param(initialize=hist_monthly_heat_peak_energy)
    # Demand data of agents
    model.Pdem = pyo.Param(model.I, model.T, initialize=lambda m, i, t: elec_consumption.iloc[i, t])
    model.Hhw = pyo.Param(model.I, model.T, initialize=lambda m, i, t: hot_water_heatdem.iloc[i, t])
    model.Hsh = pyo.Param(model.I, model.T, initialize=lambda m, i, t: space_heating_heatdem.iloc[i, t])
    model.Cld = pyo.Param(model.I, model.T, initialize=lambda m, i, t: cold_consumption.iloc[i, t])
    # Supply data of agents
    model.Ppv = pyo.Param(model.I, model.T, initialize=lambda m, i, t: pv_production.iloc[i, t])
    model.Hsh_excess_low_temp = pyo.Param(model.I, model.T, initialize=lambda m, i, t: excess_low_temp_heat.iloc[i, t])
    model.Hsh_excess_high_temp = pyo.Param(model.I, model.T,
                                           initialize=lambda m, i, t: excess_high_temp_heat.iloc[i, t])
    # BES data
    model.effe = pyo.Param(initialize=battery_efficiency)
    model.SOCBES0 = pyo.Param(model.I, initialize=SOCBES0)
    model.Emax_BES = pyo.Param(model.I, initialize=battery_capacity)
    model.Pmax_BES_Cha = pyo.Param(model.I, initialize=battery_charge_rate)
    model.Pmax_BES_Dis = pyo.Param(model.I, initialize=battery_discharge_rate)
    # Building inertia as thermal energy storage
    model.BITES_Eshallow0 = pyo.Param(model.I, initialize=lambda m, i: BITES_Eshallow0[i])
    model.BITES_Edeep0 = pyo.Param(model.I, initialize=lambda m, i: BITES_Edeep0[i])
    model.Energy_shallow_cap = pyo.Param(model.I, initialize=lambda m, i: 0.046 * build_area[i])
    model.Energy_deep_cap = pyo.Param(model.I, initialize=lambda m, i: 0.291 * build_area[i])
    model.Heat_rate_shallow = pyo.Param(model.I, initialize=lambda m, i: 0.023 * build_area[i])
    model.Kval = pyo.Param(model.I, initialize=lambda m, i: 0.03 * build_area[i])
    model.Kloss_shallow = pyo.Param(initialize=0.9913)
    model.Kloss_deep = pyo.Param(initialize=0.9963)
    # Heat pump data
    model.COPhp = pyo.Param(model.I, initialize=heatpump_COP)
    model.Phpmax = pyo.Param(model.I, initialize=heatpump_max_power)
    model.Hhpmax = pyo.Param(model.I, initialize=heatpump_max_heat)
    model.HP_Cproduct_active = pyo.Param(model.I, initialize=lambda m, i: HP_Cproduct_active[i])
    # Booster heat pump data
    model.COPhpB = pyo.Param(model.I, initialize=booster_heatpump_COP)
    model.PhpBmax = pyo.Param(model.I, initialize=booster_heatpump_max_power)
    model.HhpBmax = pyo.Param(model.I, initialize=booster_heatpump_max_heat)
    # Chiller data
    model.COPcc = pyo.Param(initialize=chiller_COP)
    model.chiller_heat_recovery = pyo.Param(initialize=chiller_heat_recovery)
    model.Pccmax = pyo.Param(initialize=Pccmax)
    # Borehole
    model.borehole = pyo.Param(model.I, initialize=lambda m, i: borehole[i])
    # Thermal energy storage data
    model.efft = pyo.Param(model.I, initialize=thermalstorage_efficiency)
    model.SOCTES0 = pyo.Param(model.I, initialize=SOCTES0)
    model.Tmax_TES = pyo.Param(model.I, initialize=thermalstorage_max_temp)
    model.kwh_per_deg = pyo.Param(model.I, initialize=kwh_per_deg)
    # Local heat network efficiency
    model.Heat_trans_loss = pyo.Param(initialize=heat_trans_loss)
    model.cold_trans_loss = pyo.Param(initialize=cold_trans_loss)
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
    model.Cbuy_grid = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Csell_grid = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Pcha = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Pdis = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.SOCBES = pyo.Var(model.I, model.T, bounds=(0, 1), within=pyo.NonNegativeReals,
                           initialize=lambda m, i, t: SOCBES0[i])
    model.Hhp = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Chp = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Php = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.HTEScha = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.HTESdis = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.SOCTES = pyo.Var(model.I, model.T, bounds=(0, 1), within=pyo.NonNegativeReals,
                           initialize=lambda m, i, t: SOCTES0[i])
    model.Ccc = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Hcc = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Pcc = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Energy_shallow = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    # Charge/discharge of the shallow layer, a negative value meaning discharge
    model.Hcha_shallow = pyo.Var(model.I, model.T, within=pyo.Reals, initialize=0)
    model.Flow = pyo.Var(model.I, model.T, within=pyo.Reals, initialize=0)
    model.Loss_shallow = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Energy_deep = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.Loss_deep = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    if summer_mode:
        model.HhpB = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
        model.PhpB = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    model.heat_dump = pyo.Var(model.I, model.T, within=pyo.NonNegativeReals, initialize=0)
    # This variable will keep track of the unused excess cooling for us. No penalty associated with it - this cooling
    # can be used, or not, it's fine either way
    model.cool_dump = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0)
    # Electrical and heat load peaks
    model.daily_elec_peak_load = pyo.Var(within=pyo.NonNegativeReals, initialize=0)
    model.avg_elec_peak_load = pyo.Var(within=pyo.NonNegativeReals, initialize=sum(hist_top_three_elec_peak_load) / 3.0)
    model.daily_heat_peak_energy = pyo.Var(within=pyo.NonNegativeReals, initialize=0)
    model.monthly_heat_peak_energy = pyo.Var(within=pyo.NonNegativeReals, initialize=0)

    add_obj_and_constraints(model, summer_mode, month)

    # Solve!
    results = solver.solve(model)
    return model, results


def add_obj_and_constraints(model: pyo.ConcreteModel, summer_mode: bool, month: int):
    # Objective function:
    model.obj = pyo.Objective(rule=obj_rul, sense=pyo.minimize)
    model.con_max_Pbuy_grid = pyo.Constraint(model.I, model.T, rule=max_Pbuy_grid)
    model.con_max_Hbuy_grid = pyo.Constraint(model.I, model.T, rule=max_Hbuy_grid)
    model.con_max_Psell_grid = pyo.Constraint(model.I, model.T, rule=max_Psell_grid)
    model.con_max_Pbuy_market = pyo.Constraint(model.T, rule=max_Pbuy_market)
    model.con_max_Psell_market = pyo.Constraint(model.T, rule=max_Psell_market)
    model.con_max_Hsell_grid = pyo.Constraint(model.I, model.T, rule=max_Hsell_grid)
    if summer_mode:
        model.con_agent_Pbalance_summer = pyo.Constraint(model.I, model.T, rule=agent_Pbalance_summer)
        model.con_agent_Hbalance_summer = pyo.Constraint(model.I, model.T, rule=agent_Hbalance_summer)
        model.con_HTES_supplied_by_Bhp = pyo.Constraint(model.I, model.T, rule=HTES_supplied_by_Bhp)
    else:
        model.con_agent_Pbalance_winter = pyo.Constraint(model.I, model.T, rule=agent_Pbalance_winter)
        model.con_agent_Hbalance_winter = pyo.Constraint(model.I, model.T, rule=agent_Hbalance_winter)

    if month in [6, 7, 8]:
        model.con_agent_Cbalance_summer = pyo.Constraint(model.I, model.T, rule=agent_Cbalance_summer)
    else:
        model.con_agent_Cbalance_winter = pyo.Constraint(model.I, model.T, rule=agent_Cbalance_winter)
    model.con_Hhw_supplied_by_HTES = pyo.Constraint(model.I, model.T, rule=Hhw_supplied_by_HTES)
    model.con_BITES_Eshallow_balance = pyo.Constraint(model.I, model.T, rule=BITES_Eshallow_balance)
    model.con_BITES_shallow_dis = pyo.Constraint(model.I, model.T, rule=BITES_shallow_dis)
    model.con_BITES_shallow_cha = pyo.Constraint(model.I, model.T, rule=BITES_shallow_cha)
    model.con_BITES_Edeep_balance = pyo.Constraint(model.I, model.T, rule=BITES_Edeep_balance)
    model.con_BITES_Eflow_between_storages = pyo.Constraint(model.I, model.T, rule=BITES_Eflow_between_storages)
    model.con_BITES_shallow_loss = pyo.Constraint(model.I, model.T, rule=BITES_shallow_loss)
    model.con_BITES_deep_loss = pyo.Constraint(model.I, model.T, rule=BITES_deep_loss)
    model.con_BITES_max_Hdis_shallow = pyo.Constraint(model.I, model.T, rule=BITES_max_Hdis_shallow)
    model.con_BITES_max_Hcha_shallow = pyo.Constraint(model.I, model.T, rule=BITES_max_Hcha_shallow)
    model.con_BITES_max_Eshallow = pyo.Constraint(model.I, model.T, rule=BITES_max_Eshallow)
    model.con_BITES_max_Edeep = pyo.Constraint(model.I, model.T, rule=BITES_max_Edeep)
    model.con_LEC_Pbalance = pyo.Constraint(model.T, rule=LEC_Pbalance)
    model.con_LEC_Hbalance = pyo.Constraint(model.T, rule=LEC_Hbalance)
    model.con_LEC_Cbalance = pyo.Constraint(model.T, rule=LEC_Cbalance)
    model.con_BES_max_dis = pyo.Constraint(model.I, model.T, rule=BES_max_dis)
    model.con_BES_max_cha = pyo.Constraint(model.I, model.T, rule=BES_max_cha)
    model.con_BES_Ebalance = pyo.Constraint(model.I, model.T, rule=BES_Ebalance)
    model.con_BES_final_SOC = pyo.Constraint(model.I, rule=BES_final_SOC)
    model.con_BES_remove_binaries = pyo.Constraint(model.I, model.T, rule=BES_remove_binaries)
    model.con_HP_Hproduct = pyo.Constraint(model.I, model.T, rule=HP_Hproduct)
    model.con_HP_Cproduct = pyo.Constraint(model.I, model.T, rule=HP_Cproduct)
    model.con_max_HP_Hproduct = pyo.Constraint(model.I, model.T, rule=max_HP_Hproduct)
    model.con_max_HP_Pconsumption = pyo.Constraint(model.I, model.T, rule=max_HP_Pconsumption)
    if summer_mode:
        model.con_max_booster_HP_Hproduct_summer = pyo.Constraint(model.I, model.T, rule=max_booster_HP_Hproduct_summer)
        model.con_chiller_Hwaste_summer = pyo.Constraint(model.T, rule=chiller_Hwaste_summer)
    else:
        model.con_chiller_Hwaste_winter = pyo.Constraint(model.T, rule=chiller_Hwaste_winter)
    #    model.con_max_HTES_dis = pyo.Constraint(model.I, model.T, rule=max_HTES_dis)
    #    model.con_max_HTES_cha = pyo.Constraint(model.I, model.T, rule=max_HTES_cha)
    model.con_HTES_Ebalance = pyo.Constraint(model.I, model.T, rule=HTES_Ebalance)
    model.con_HTES_final_SOC = pyo.Constraint(model.I, rule=HTES_final_SOC)
    model.con_chiller_Cpower_product = pyo.Constraint(model.T, rule=chiller_Cpower_product)
    model.con_max_chiller_Cpower_product = pyo.Constraint(model.T, rule=max_chiller_Cpower_product)
    model.con_elec_peak_load1 = pyo.Constraint(model.T, rule=elec_peak_load1)
    model.con_elec_peak_load2 = pyo.Constraint(rule=elec_peak_load2)
    model.con_elec_peak_load3 = pyo.Constraint(rule=elec_peak_load3)
    model.con_heat_peak_load1 = pyo.Constraint(rule=heat_peak_load1)
    model.con_heat_peak_load2 = pyo.Constraint(rule=heat_peak_load2)
    model.con_heat_peak_load3 = pyo.Constraint(rule=heat_peak_load3)


# Objective function: minimize the total charging cost (eq. 1 of the report)
def obj_rul(model):
    return sum(
        # Electricity cost terms:
        model.Pbuy_market[t] * (model.nordpool_price[t] + model.elec_trans_fee + model.elec_tax_fee)  # Purchasing cost
        - model.Psell_market[t] * (model.nordpool_price[t] + model.incentive_fee)  # Selling cost
        + model.avg_elec_peak_load * model.elec_peak_load_fee  # Peak load cost

        # Heat cost terms:
        + model.Hbuy_market[t] * model.Hprice_energy  # Purchasing cost
        + (model.monthly_heat_peak_energy / 24) * model.heat_peak_load_fee  # Peak load cost

        # Penalty terms
        + sum(model.heat_dump[i, t] for i in model.I) * model.penalty  # Extra heating power generation dumping
        for t in model.T)


# Constraints:
# Buying and selling heat/electricity from agents cannot happen at the same time
# and should be restricted to its maximum value (Pmax_grid) (eqs. 10 to 15 of the report)
def max_Pbuy_grid(model, i, t):
    return model.Pbuy_grid[i, t] <= model.Pmax_grid * model.U_power_buy_sell_grid[i, t]


def max_Hbuy_grid(model, i, t):
    return model.Hbuy_grid[i, t] <= model.Hmax_grid  # * model.U_heat_buy_sell_grid[i, t]


def max_Psell_grid(model, i, t):
    return model.Psell_grid[i, t] <= model.Pmax_grid * (1 - model.U_power_buy_sell_grid[i, t])


def max_Hsell_grid(model, i, t):
    return model.Hsell_grid[i, t] <= model.Hmax_grid


# Buying and selling power from the market cannot happen at the same time
# and should be restricted to its maximum value (Pmax_market) (eqs. 2 and 4 of the report)
def max_Pbuy_market(model, t):
    return model.Pbuy_market[t] <= model.Pmax_market * model.U_buy_sell_market[t]


def max_Psell_market(model, t):
    return model.Psell_market[t] <= model.Pmax_market * (1 - model.U_buy_sell_market[t])


# Electric and heat peak load constraints
def elec_peak_load1(model, t):
    return model.daily_elec_peak_load >= model.Pbuy_market[t] - model.Psell_market[t]


def elec_peak_load2(model):
    return model.avg_elec_peak_load >= (model.hist_top_three_elec_peak_load[0]
                                        + model.hist_top_three_elec_peak_load[1]
                                        + model.daily_elec_peak_load) / 3


def elec_peak_load3(model):
    return model.avg_elec_peak_load >= (model.hist_top_three_elec_peak_load[0]
                                        + model.hist_top_three_elec_peak_load[1]
                                        + model.hist_top_three_elec_peak_load[2]) / 3


def heat_peak_load1(model):
    return model.daily_heat_peak_energy >= sum(model.Hbuy_market[t] for t in model.T)


def heat_peak_load2(model):
    return model.monthly_heat_peak_energy >= model.daily_heat_peak_energy


def heat_peak_load3(model):
    return model.monthly_heat_peak_energy >= model.Hist_monthly_heat_peak_energy


# (eq. 2 and 3 of the report)
# Electrical/heat/cool power balance equation for agents
def agent_Pbalance_winter(model, i, t):
    # Only used in winter mode
    return model.Ppv[i, t] + model.Pdis[i, t] + model.Pbuy_grid[i, t] == \
        model.Pdem[i, t] + model.Php[i, t] + model.Pcha[i, t] + model.Psell_grid[i, t]


def agent_Pbalance_summer(model, i, t):
    # Only used in summer mode
    return model.Ppv[i, t] + model.Pdis[i, t] + model.Pbuy_grid[i, t] == \
        model.Pdem[i, t] + model.Php[i, t] + model.PhpB[i, t] + model.Pcha[i, t] + model.Psell_grid[i, t]


def agent_Hbalance_winter(model, i, t):
    # Only used in winter mode
    # Note that "Hsh_excess_low_temp" isn't used here, even though it theoretically could be used to fill low-temp
    # space heating need (Hsh).
    # with TES
    if model.kwh_per_deg[i] != 0:
        return model.Hbuy_grid[i, t] + model.Hhp[i, t] + model.Hsh_excess_high_temp[i, t] == \
            model.Hsell_grid[i, t] + model.Hcha_shallow[i, t] + model.Hsh[i, t] \
            + model.HTEScha[i, t] + model.heat_dump[i, t]
    # without TES
    else:
        return model.Hbuy_grid[i, t] + model.Hhp[i, t] + model.Hsh_excess_high_temp[i, t] == \
            model.Hsell_grid[i, t] + model.Hcha_shallow[i, t] + model.Hsh[i, t] \
            + model.Hhw[i, t] + model.heat_dump[i, t]


def agent_Hbalance_summer(model, i, t):
    # Only used in summer mode
    # with TES
    if model.kwh_per_deg[i] != 0:
        return model.Hbuy_grid[i, t] + model.Hhp[i, t] + model.Hsh_excess_high_temp[i, t] \
            + model.Hsh_excess_low_temp[i, t] == model.Hsell_grid[i, t] + model.Hcha_shallow[i, t] \
            + model.Hsh[i, t] + PERC_OF_HT_COVERABLE_BY_LT * model.HTEScha[i, t] + model.heat_dump[i, t]
    # without TES
    else:
        return model.Hbuy_grid[i, t] + model.Hhp[i, t] + model.Hsh_excess_high_temp[i, t] \
            + model.Hsh_excess_low_temp[i, t] == model.Hsell_grid[i, t] + model.Hcha_shallow[i, t] \
            + model.Hsh[i, t] + PERC_OF_HT_COVERABLE_BY_LT * model.Hhw[i, t] + model.heat_dump[i, t]


def agent_Cbalance_winter(model, i, t):
    # Only used in months [1 to 5, 9 to 12]
    # with free cooling from borehole (model.borehole[i] == 1)
    # without free cooling from borehole (model.borehole[i] == 0)
    return model.Cbuy_grid[i, t] + model.Chp[i, t] == model.Csell_grid[i, t] + model.Cld[i, t] * (1 - model.borehole[i])


def agent_Cbalance_summer(model, i, t):
    # Only used in months [6, 7, 8]
    return model.Cbuy_grid[i, t] + model.Chp[i, t] == model.Csell_grid[i, t] + model.Cld[i, t]


# (eq. 5 and 6 of the report)
def HTES_supplied_by_Bhp(model, i, t):
    # Only used in summer mode
    # with TES
    if model.kwh_per_deg[i] != 0:
        return model.HhpB[i, t] == (1 - PERC_OF_HT_COVERABLE_BY_LT) * model.HTEScha[i, t]
    # without TES
    else:
        return model.HhpB[i, t] == (1 - PERC_OF_HT_COVERABLE_BY_LT) * model.Hhw[i, t]


def Hhw_supplied_by_HTES(model, i, t):
    # with TES
    if model.kwh_per_deg[i] != 0:
        return model.HTESdis[i, t] == model.Hhw[i, t]
    # without TES
    else:
        return pyo.Constraint.Skip


# (eqs. 22 to 28 of the report)
def BITES_Eshallow_balance(model, i, t):
    if t == 0:
        return model.Energy_shallow[i, 0] == model.BITES_Eshallow0[i] + model.Hcha_shallow[i, 0] \
            - model.Flow[i, 0] - model.Loss_shallow[i, 0]
    else:
        return model.Energy_shallow[i, t] == model.Energy_shallow[i, t - 1] + model.Hcha_shallow[i, t] \
            - model.Flow[i, t] - model.Loss_shallow[i, t]


def BITES_shallow_dis(model, i, t):
    # Negative charge means discharge
    return -model.Hcha_shallow[i, t] <= model.Heat_rate_shallow[i]


def BITES_shallow_cha(model, i, t):
    return model.Hcha_shallow[i, t] <= model.Heat_rate_shallow[i]


def BITES_Edeep_balance(model, i, t):
    if t == 0:
        return model.Energy_deep[i, 0] == model.BITES_Edeep0[i] + model.Flow[i, 0] - model.Loss_deep[i, 0]
    else:
        return model.Energy_deep[i, t] == model.Energy_deep[i, t - 1] + model.Flow[i, t] - model.Loss_deep[i, t]


def BITES_Eflow_between_storages(model, i, t):
    if (model.Energy_shallow_cap[i] == 0) or (model.Energy_deep_cap[i] == 0):
        return model.Flow[i, t] == 0
    return model.Flow[i, t] == ((model.Energy_shallow[i, t] / model.Energy_shallow_cap[i])
                                - (model.Energy_deep[i, t] / model.Energy_deep_cap[i])) * model.Kval[i]


def BITES_max_Eshallow(model, i, t):
    return model.Energy_shallow[i, t] <= model.Energy_shallow_cap[i]


def BITES_max_Edeep(model, i, t):
    return model.Energy_deep[i, t] <= model.Energy_deep_cap[i]


def BITES_shallow_loss(model, i, t):
    if t == 0:
        return model.Loss_shallow[i, 0] == 0
    else:
        return model.Loss_shallow[i, t] == model.Energy_shallow[i, t - 1] * (1 - model.Kloss_shallow)


def BITES_deep_loss(model, i, t):
    if t == 0:
        return model.Loss_deep[i, 0] == 0
    else:
        return model.Loss_deep[i, t] == model.Energy_deep[i, t - 1] * (1 - model.Kloss_deep)


def BITES_max_Hdis_shallow(model, i, t):
    # Negative charge means discharge
    return -model.Hcha_shallow[i, t] <= model.Hsh[i, t]


def BITES_max_Hcha_shallow(model, i, t):
    return model.Hcha_shallow[i, t] <= model.Hhpmax[i] + model.Hmax_grid - model.Hsh[i, t]


# Electrical/heat/cool power balance equation for grid (eqs. 7 to 9 of the report)
def LEC_Pbalance(model, t):
    return sum(model.Psell_grid[i, t] for i in model.I) + model.Pbuy_market[t] == \
        sum(model.Pbuy_grid[i, t] for i in model.I) + model.Psell_market[t] + model.Pcc[t]


def LEC_Hbalance(model, t):
    return sum(model.Hsell_grid[i, t] * (1 - model.Heat_trans_loss) for i in model.I) + \
        model.Hbuy_market[t] * (1 - model.Heat_trans_loss) + model.Hcc[t] * (1 - model.Heat_trans_loss) \
        == sum(model.Hbuy_grid[i, t] for i in model.I)


def LEC_Cbalance(model, t):
    return model.Ccc[t] + sum(model.Csell_grid[i, t] * (1 - model.cold_trans_loss) for i in model.I) == \
        sum(model.Cbuy_grid[i, t] for i in model.I) + model.cool_dump[t]


# Battery energy storage model (eqs. 16 to 19 of the report)
# Maximum charging/discharging power limitations
def BES_max_dis(model, i, t):
    return model.Pdis[i, t] <= model.Pmax_BES_Dis[i]


def BES_max_cha(model, i, t):
    return model.Pcha[i, t] <= model.Pmax_BES_Cha[i]


# State of charge modelling
def BES_Ebalance(model, i, t):
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


def BES_final_SOC(model, i):
    return model.SOCBES[i, len(model.T) - 1] == model.SOCBES0[i]


def BES_remove_binaries(model, i, t):
    if (model.Pmax_BES_Dis[i] == 0) or (model.Pmax_BES_Cha[i] == 0):
        # Can't charge/discharge
        return model.Pcha[i, t] + model.Pdis[i, t] <= 0
    return model.Pdis[i, t] / model.Pmax_BES_Dis[i] + model.Pcha[i, t] / model.Pmax_BES_Cha[i] <= 1


# Heat pump model (eq. 20 of the report)
def HP_Hproduct(model, i, t):
    return model.Hhp[i, t] == model.COPhp[i] * model.Php[i, t]


def HP_Cproduct(model, i, t):
    if model.HP_Cproduct_active[i]:
        return model.Chp[i, t] == (model.COPhp[i] - 1) * model.Php[i, t]
    else:
        return model.Chp[i, t] == 0


def max_HP_Hproduct(model, i, t):
    return model.Hhp[i, t] <= model.Hhpmax[i]


def max_HP_Pconsumption(model, i, t):
    return model.Php[i, t] <= model.Phpmax[i]


# Booster heat pump model (eq. 20 of the report)
def booster_HP_Hproduct(model, i, t):
    # Only used in summer mode
    return model.HhpB[i, t] == model.COPhpB[i] * model.PhpB[i, t]


def max_booster_HP_Hproduct_summer(model, i, t):
    # Only used in summer mode
    return model.HhpB[i, t] <= model.HhpBmax[i]


# Thermal energy storage model (eqs. 32 to 25 of the report)
# Maximum/minimum temperature limitations of hot water inside TES
# def max_HTES_dis(model, i, t):
#     return model.HTESdis[i, t] <= model.kwh_per_deg[i] * model.Tmax_TES[i]
#
#
# def max_HTES_cha(model, i, t):
#     return model.HTEScha[i, t] <= model.kwh_per_deg[i] * model.Tmax_TES[i]


# State of charge modelling
def HTES_Ebalance(model, i, t):
    if model.kwh_per_deg[i] == 0:
        # No storage capacity, then we need to ensure that charge and discharge are 0 as well.
        return model.HTESdis[i, t] + model.HTEScha[i, t] == model.kwh_per_deg[i]
    # We assume that model.efft and model.Tmax_TES cannot be 0
    charge = model.HTEScha[i, t] * model.efft[i] / (model.kwh_per_deg[i] * model.Tmax_TES[i])
    discharge = model.HTESdis[i, t] / ((model.kwh_per_deg[i] * model.Tmax_TES[i]) * model.efft[i])
    charge_change = charge - discharge
    if t == 0:
        return model.SOCTES[i, 0] == model.SOCTES0[i] + charge_change
    else:
        return model.SOCTES[i, t] == model.SOCTES[i, t - 1] + charge_change


def HTES_final_SOC(model, i):
    return model.SOCTES[i, len(model.T) - 1] == model.SOCTES0[i]


# Compression chiller model (eqs. 29 to 31 of the report)
def chiller_Cpower_product(model, t):
    return model.Ccc[t] == model.COPcc * model.Pcc[t]


def max_chiller_Cpower_product(model, t):
    return model.Pcc[t] <= model.Pccmax


def chiller_Hwaste_summer(model, t):
    # Only used in summer mode
    return model.Hcc[t] == (1 + model.COPcc) * model.Pcc[t] * model.chiller_heat_recovery


def chiller_Hwaste_winter(model, t):
    # Only used in winter mode : Due to high temperature of district heating (60 deg. C),
    # it is not possible to export heat from building to the district heating
    return model.Hcc[t] <= 0
