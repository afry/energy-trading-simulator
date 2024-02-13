import datetime
import logging
from typing import Any, Dict, List, Tuple

import numpy as np

import pandas as pd

import pyomo.environ as pyo
from pyomo.opt import OptSolver, SolverResults

from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market, Trade
from tradingplatformpoc.simulation_runner import optimization_problem
from tradingplatformpoc.trading_platform_utils import add_to_nested_dict

logger = logging.getLogger(__name__)


"""
Here we keep methods that do either
 1. Construct inputs to Chalmers' solve_model function, from agent data
 2. Translate the optimized pyo.ConcreteModel back to our domain (Trades, metadata etc)
"""


class ChalmersOutputs:
    trades: List[Trade]
    battery_storage_levels: Dict[str, Dict[datetime.datetime, float]]  # (agent_guid, (period, storage_level))
    hp_workloads: Dict[str, Dict[datetime.datetime, float]]  # (agent_guid, (period, storage_level))

    def __init__(self, trades: List[Trade],
                 battery_storage_levels: Dict[str, Dict[datetime.datetime, float]],
                 hp_workloads: Dict[str, Dict[datetime.datetime, float]]):
        self.trades = trades
        self.battery_storage_levels = battery_storage_levels
        self.hp_workloads = hp_workloads


def optimize(solver: OptSolver,
             agents: List[IAgent],
             grid_agents: Dict[Resource, GridAgent],
             area_info: Dict[str, Any],
             start_datetime: datetime.datetime,
             trading_horizon: int) -> ChalmersOutputs:
    agents = [agent for agent in agents if not isinstance(agent, GridAgent)]  # Filter out grid agents
    agent_guids = [agent.guid for agent in agents]
    # The order specified in "agents" will be used throughout

    elec_demand_df, elec_supply_df, high_heat_demand_df, high_heat_supply_df, \
        low_heat_demand_df, low_heat_supply_df, cooling_demand_df, cooling_supply_df = \
        build_supply_and_demand_dfs(agents, start_datetime, trading_horizon)

    # battery_capacities = [agent.battery.capacity_kwh for agent in agents]
    # heatpump_max_power = [agent.heat_pump_max_input for agent in agents]
    # heatpump_max_heat = [agent.heat_pump_max_output for agent in agents]

    # The following will be extracted from area_info:
    # area_info['TradingHorizon']
    # area_info['BatteryChargeRate']
    # area_info['BatteryDischargeRate']
    # area_info['BatteryEfficiency']
    # area_info['BatteryEndChargeLevel']
    # area_info['PVEfficiency']
    # area_info['COPHeatPumps']
    # area_info['COPCompChiller']

    # WIP: Add more stuff here

    # Question-marks:
    # energy_shallow_cap, energy_deep_cap - capacity of thermal energy storage [kWh] - specify? calculate from sqm?

    optimized_model, results = optimization_problem.mock_opt_problem(solver)

    elec_grid_agent_guid = grid_agents[Resource.ELECTRICITY].guid
    return extract_outputs(optimized_model, results, start_datetime, elec_grid_agent_guid, agent_guids)


def extract_outputs(optimized_model: pyo.ConcreteModel,
                    solver_results: SolverResults,
                    start_datetime: datetime.datetime,
                    grid_agent_guid: str,
                    agent_guids: List[str]) -> ChalmersOutputs:
    elec_trades = get_power_transfers(optimized_model, start_datetime, grid_agent_guid, agent_guids)
    # TODO: add heat trades, maybe cooling too, here...
    battery_storage_levels = get_value_per_agent(optimized_model, start_datetime, 'SOCBES', agent_guids)
    hp_workloads = get_value_per_agent(optimized_model, start_datetime, 'Hhp', agent_guids)
    return ChalmersOutputs(elec_trades, battery_storage_levels, hp_workloads)


def build_supply_and_demand_dfs(agents: List[IAgent], start_datetime: datetime.datetime, trading_horizon: int) -> \
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
              pd.DataFrame]:
    elec_demand = []
    elec_supply = []
    high_heat_demand = []
    high_heat_supply = []
    low_heat_demand = []
    low_heat_supply = []
    cooling_demand = []
    cooling_supply = []
    for agent in agents:
        agent_elec_demand: List[float] = []
        agent_elec_supply: List[float] = []
        agent_high_heat_demand: List[float] = []
        agent_high_heat_supply: List[float] = []
        agent_low_heat_demand: List[float] = []
        agent_low_heat_supply: List[float] = []
        agent_cooling_demand: List[float] = []
        agent_cooling_supply: List[float] = []
        for hour in range(trading_horizon):
            usage_per_resource = agent.get_actual_usage(start_datetime + datetime.timedelta(hours=hour))
            add_usage_to_demand_list(agent_elec_demand, usage_per_resource[Resource.ELECTRICITY])
            add_usage_to_supply_list(agent_elec_supply, usage_per_resource[Resource.ELECTRICITY])
            add_usage_to_demand_list(agent_high_heat_demand, usage_per_resource[Resource.HIGH_TEMP_HEAT])
            add_usage_to_supply_list(agent_high_heat_supply, usage_per_resource[Resource.HIGH_TEMP_HEAT])
            add_usage_to_demand_list(agent_low_heat_demand, usage_per_resource[Resource.LOW_TEMP_HEAT])
            add_usage_to_supply_list(agent_low_heat_supply, usage_per_resource[Resource.LOW_TEMP_HEAT])
            add_usage_to_demand_list(agent_cooling_demand, usage_per_resource[Resource.COOLING])
            add_usage_to_supply_list(agent_cooling_supply, usage_per_resource[Resource.COOLING])
        elec_demand.append(agent_elec_demand)
        elec_supply.append(agent_elec_supply)
        high_heat_demand.append(agent_high_heat_demand)
        high_heat_supply.append(agent_high_heat_supply)
        low_heat_demand.append(agent_low_heat_demand)
        low_heat_supply.append(agent_low_heat_supply)
        cooling_demand.append(agent_cooling_demand)
        cooling_supply.append(agent_cooling_supply)
    elec_demand_df = pd.DataFrame(elec_demand)
    elec_supply_df = pd.DataFrame(elec_supply)
    high_heat_demand_df = pd.DataFrame(high_heat_demand)
    high_heat_supply_df = pd.DataFrame(high_heat_supply)
    low_heat_demand_df = pd.DataFrame(low_heat_demand)
    low_heat_supply_df = pd.DataFrame(low_heat_supply)
    cooling_demand_df = pd.DataFrame(cooling_demand)
    cooling_supply_df = pd.DataFrame(cooling_supply)
    return (elec_demand_df, elec_supply_df, high_heat_demand_df, high_heat_supply_df,
            low_heat_demand_df, low_heat_supply_df, cooling_demand_df, cooling_supply_df)


def add_usage_to_demand_list(agent_list: List[float], usage_of_resource: float):
    agent_list.append(usage_of_resource if usage_of_resource > 0 else 0)


def add_usage_to_supply_list(agent_list: List[float], usage_of_resource: float):
    agent_list.append(-usage_of_resource if usage_of_resource < 0 else 0)


def get_power_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime, grid_agent_guid: str,
                        agent_guids: List[str]) -> List[Trade]:
    # For example: Pbuy_market is how much the LEC bought from the external grid operator
    return get_transfers(optimized_model, start_datetime,
                         sold_to_external_name='Psell_market', bought_from_external_name='Pbuy_market',
                         sold_internal_name='Psell_grid', bought_internal_name='Pbuy_grid',
                         resource=Resource.ELECTRICITY, grid_agent_guid=grid_agent_guid, agent_guids=agent_guids)


def get_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                  sold_to_external_name: str, bought_from_external_name: str,
                  sold_internal_name: str, bought_internal_name: str, resource: Resource, grid_agent_guid: str,
                  agent_guids: List[str]) -> List[Trade]:
    transfers = []
    for hour in optimized_model.time:
        trade = construct_external_trade(bought_from_external_name, hour, optimized_model, sold_to_external_name,
                                         start_datetime, grid_agent_guid, resource)
        transfers.append(trade)
        for i_agent in optimized_model.agent:
            t = construct_agent_trade(bought_internal_name, sold_internal_name, hour, i_agent, optimized_model,
                                      start_datetime, resource, agent_guids)
            transfers.append(t)
    return transfers


def construct_agent_trade(bought_internal_name: str, sold_internal_name: str, hour: int, i_agent: int,
                          optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime, resource: Resource,
                          agent_guids: List[str]) -> Trade:
    quantity = pyo.value(getattr(optimized_model, bought_internal_name)[i_agent, hour]
                         - getattr(optimized_model, sold_internal_name)[i_agent, hour])
    agent_name = agent_guids[i_agent]
    return Trade(period=start_datetime + datetime.timedelta(hours=hour),
                 action=Action.BUY if quantity > 0 else Action.SELL, resource=resource,
                 quantity=abs(quantity), price=np.nan, source=agent_name, by_external=False, market=Market.LOCAL)


def construct_external_trade(bought_from_external_name: str, hour: int, optimized_model: pyo.ConcreteModel,
                             sold_to_external_name: str, start_datetime: datetime.datetime, grid_agent_guid: str,
                             resource: Resource) -> Trade:
    external_quantity = pyo.value(getattr(optimized_model, sold_to_external_name)[hour]
                                  - getattr(optimized_model, bought_from_external_name)[hour])
    return Trade(period=start_datetime + datetime.timedelta(hours=hour),
                 action=Action.BUY if external_quantity > 0 else Action.SELL, resource=resource,
                 quantity=abs(external_quantity), price=np.nan, source=grid_agent_guid, by_external=True,
                 market=Market.LOCAL)


def add_value_per_agent_to_dict(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                                dict_to_add_to: Dict[str, Dict[datetime.datetime, Any]],
                                variable_name: str, agent_guids: List[str]):
    """
    Example variable names: Hhp for heat pump production, SOCBES for state of charge of battery storage
    """
    for hour in optimized_model.time:
        for i_agent in optimized_model.agent:
            quantity = pyo.value(getattr(optimized_model, variable_name)[i_agent, hour])
            period = start_datetime + datetime.timedelta(hours=hour)
            add_to_nested_dict(dict_to_add_to, agent_guids[i_agent], period, quantity)


def get_value_per_agent(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                        variable_name: str, agent_guids: List[str]) -> Dict[str, Dict[datetime.datetime, Any]]:
    """
    Example variable names: Hhp for heat pump production, SOCBES for state of charge of battery storage
    """
    dict_to_add_to: Dict[str, Dict[datetime.datetime, Any]] = {}
    for hour in optimized_model.time:
        for i_agent in optimized_model.agent:
            quantity = pyo.value(getattr(optimized_model, variable_name)[i_agent, hour])
            period = start_datetime + datetime.timedelta(hours=hour)
            add_to_nested_dict(dict_to_add_to, agent_guids[i_agent], period, quantity)
    return dict_to_add_to
