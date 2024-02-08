import datetime
import logging
from typing import Any, Dict, List, Tuple

import numpy as np

import pandas as pd

import pyomo.environ as pyo

from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market, Trade
from tradingplatformpoc.trading_platform_utils import add_to_nested_dict

logger = logging.getLogger(__name__)


"""
Here we keep methods that do either
 1. Construct inputs to Chalmers' solve_model function, from agent data
 2. Translate the optimized pyo.ConcreteModel back to our domain (Trades, metadata etc)
"""


def build_inputs(agents: List[IAgent], area_info: Dict[str, Any], start_datetime: datetime.datetime,
                 trading_horizon: int):
    block_agents = [agent for agent in agents if isinstance(agent, BlockAgent)]
    # block_agent_guids = [agent.guid for agent in block_agents]
    # The order specified in block_agents will be used throughout

    elec_demand_df, elec_supply_df, high_heat_demand_df, high_heat_supply_df, \
        low_heat_demand_df, low_heat_supply_df, cooling_demand_df, cooling_supply_df = \
        build_supply_and_demand_dfs(block_agents, start_datetime, trading_horizon)

    # battery_capacities = [agent.battery.capacity_kwh for agent in block_agents]
    # heatpump_max_power = [agent.heat_pump_max_input for agent in block_agents]
    # heatpump_max_heat = [agent.heat_pump_max_output for agent in block_agents]

    # The following will be extracted from area_info:
    # area_info['BatteryChargeRate']
    # area_info['BatteryDischargeRate']
    # area_info['BatteryEfficiency']
    # area_info['PVEfficiency']
    # area_info['COP']

    # WIP: Add more stuff here

    # Question-marks:
    # heatpump_max_power, heatpump_max_heat - how to translate our stuff? Change our inputs?
    # energy_shallow_cap, energy_deep_cap - capacity of thermal energy storage [kWh] - specify? calculate from sqm?


def build_supply_and_demand_dfs(block_agents: List[BlockAgent], start_datetime: datetime.datetime,
                                trading_horizon: int) -> \
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
    for agent in block_agents:
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


def get_power_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime) -> List[Trade]:
    # For example: Pbuy_market is how much the LEC bought from the external grid operator
    return get_transfers(optimized_model, start_datetime,
                         sold_to_external_name='Psell_market', bought_from_external_name='Pbuy_market',
                         sold_internal_name='Psell_grid', bought_internal_name='Pbuy_grid')


def get_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                  sold_to_external_name: str, bought_from_external_name: str,
                  sold_internal_name: str, bought_internal_name: str) -> List[Trade]:
    transfers = []
    for hour in optimized_model.time:
        # TODO: grid_agent_guid
        trade = construct_external_trade(bought_from_external_name, hour, optimized_model, sold_to_external_name,
                                         start_datetime, 'ExternalGridAgent', Resource.ELECTRICITY)
        transfers.append(trade)
        for i_agent in optimized_model.agent:
            t = construct_agent_trade(bought_internal_name, sold_internal_name, hour, i_agent, optimized_model,
                                      start_datetime, Resource.ELECTRICITY)
            transfers.append(t)
    return transfers


def construct_agent_trade(bought_internal_name: str, sold_internal_name: str, hour: int, i_agent: int,
                          optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime, resource: Resource) \
        -> Trade:
    quantity = pyo.value(getattr(optimized_model, bought_internal_name)[i_agent, hour]
                         - getattr(optimized_model, sold_internal_name)[i_agent, hour])
    agent_name = agent_guid_from_index(optimized_model, i_agent)
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


def agent_guid_from_index(optimized_model: pyo.ConcreteModel, i_agent: int) -> str:
    # TODO: Translate index to agent GUID in some way.
    #  Perhaps use names from the input data frames on the model object, or pass it separately, into an intermediate
    #  method, which lives between trading_simulator and the Chalmers code, and then use here
    return str(i_agent)


def add_value_per_agent_to_dict(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                                dict_to_add_to: Dict[str, Dict[datetime.datetime, Any]],
                                variable_name: str):
    """
    Example variable names: Hhp for heat pump production, SOCBES for state of charge of battery storage
    """
    for hour in optimized_model.time:
        for i_agent in optimized_model.agent:
            quantity = pyo.value(getattr(optimized_model, variable_name)[i_agent, hour])
            period = start_datetime + datetime.timedelta(hours=hour)
            add_to_nested_dict(dict_to_add_to, agent_guid_from_index(optimized_model, i_agent), period, quantity)
