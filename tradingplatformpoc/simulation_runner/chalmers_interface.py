import datetime
import logging
from typing import Any, Dict, List, Tuple

import numpy as np

import pandas as pd

import pyomo.environ as pyo
from pyomo.opt import OptSolver, SolverResults

from tradingplatformpoc import constants
from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market, Trade
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.simulation_runner import CEMSSummerMode_function, CEMSWinterMode_function
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


def optimize(solver: OptSolver, agents: List[IAgent], grid_agents: Dict[Resource, GridAgent], area_info: Dict[str, Any],
             start_datetime: datetime.datetime, trading_horizon: int, elec_pricing: ElectricityPrice,
             heat_pricing: HeatingPrice) -> ChalmersOutputs:
    block_agents: List[BlockAgent] = [agent for agent in agents if isinstance(agent, BlockAgent)]
    agent_guids = [agent.guid for agent in agents]
    # The order specified in "agents" will be used throughout

    elec_demand_df, elec_supply_df, high_heat_demand_df, high_heat_supply_df, \
        low_heat_demand_df, low_heat_supply_df, cooling_demand_df, cooling_supply_df = \
        build_supply_and_demand_dfs(block_agents, start_datetime, trading_horizon)

    battery_capacities = [max(0.01, agent.battery.capacity_kwh) for agent in block_agents]  # Crashes if 0
    heatpump_max_power = [agent.heat_pump_max_input for agent in block_agents]
    heatpump_max_heat = [agent.heat_pump_max_output for agent in block_agents]

    retail_prices: pd.Series = elec_pricing.get_exact_retail_prices(start_datetime, trading_horizon, True)
    wholesale_prices: pd.Series = elec_pricing.get_exact_wholesale_prices(start_datetime, trading_horizon)
    elec_retail_prices = retail_prices.reset_index(drop=True)
    elec_wholesale_prices = wholesale_prices.reset_index(drop=True)
    heat_retail_price = heat_pricing.get_estimated_retail_price(start_datetime, True)

    # Question-marks:
    # energy_shallow_cap, energy_deep_cap - capacity of thermal energy storage [kWh] - specify? calculate from sqm?

    n_agents = len(block_agents)
    if start_datetime.month in constants.SUMMER_MODE_MONTHS:
        optimized_model, results = CEMSSummerMode_function.solve_model(solver=solver,
                                                                       n_agents=n_agents,
                                                                       external_elec_buy_price=elec_retail_prices,
                                                                       external_elec_sell_price=elec_wholesale_prices,
                                                                       external_heat_buy_price=[heat_retail_price] * 12,  # Should just be int - Chalmers code should be changed
                                                                       battery_capacity=battery_capacities,
                                                                       battery_charge_rate=[area_info['BatteryChargeRate']] * n_agents,
                                                                       battery_discharge_rate=[area_info['BatteryDischargeRate']] * n_agents,
                                                                       SOCBES0=[area_info['BatteryEndChargeLevel']] * n_agents,
                                                                       heatpump_COP=[area_info['COPHeatPumps']] * n_agents,
                                                                       heatpump_max_power=heatpump_max_power,
                                                                       heatpump_max_heat=heatpump_max_heat,
                                                                       energy_shallow_cap=[10] * n_agents,  # TODO
                                                                       energy_deep_cap=[10] * n_agents,  # TODO
                                                                       heat_rate_shallow=[0] * n_agents,  # TODO
                                                                       Kval=[0] * n_agents,  # TODO
                                                                       Kloss_shallow=[0] * n_agents,  # TODO
                                                                       Kloss_deep=[0] * n_agents,  # TODO
                                                                       elec_consumption=elec_demand_df,
                                                                       hot_water_heatdem=high_heat_demand_df,
                                                                       space_heating_heatdem=low_heat_demand_df,
                                                                       cold_consumption=cooling_demand_df,
                                                                       pv_production=elec_supply_df,
                                                                       battery_efficiency=area_info['BatteryEfficiency'],
                                                                       max_elec_transfer_between_agents=area_info['InterAgentElectricityTransferCapacity'],
                                                                       max_elec_transfer_to_external=grid_agents[Resource.ELECTRICITY].max_transfer_per_hour,
                                                                       max_heat_transfer_between_agents=area_info['InterAgentHeatTransferCapacity'],
                                                                       max_heat_transfer_to_external=grid_agents[Resource.HEATING].max_transfer_per_hour,
                                                                       chiller_COP=area_info['COPCompChiller'],
                                                                       thermalstorage_capacity=10.0,  # TODO
                                                                       thermalstorage_charge_rate=1.0,  # TODO
                                                                       thermalstorage_efficiency=1.0,  # TODO
                                                                       trading_horizon=area_info['TradingHorizon']
                                                                       )
    else:
        optimized_model, results = CEMSWinterMode_function.solve_model(solver=solver,
                                                                       n_agents=n_agents,
                                                                       external_elec_buy_price=elec_retail_prices,
                                                                       external_elec_sell_price=elec_wholesale_prices,
                                                                       external_heat_buy_price=[heat_retail_price] * 12,  # Should just be int - Chalmers code should be changed
                                                                       battery_capacity=battery_capacities,
                                                                       battery_charge_rate=[area_info['BatteryChargeRate']] * n_agents,
                                                                       battery_discharge_rate=[area_info['BatteryDischargeRate']] * n_agents,
                                                                       SOCBES0=[area_info['BatteryEndChargeLevel']] * n_agents,
                                                                       heatpump_COP=[area_info['COPHeatPumps']] * n_agents,
                                                                       heatpump_max_power=heatpump_max_power,
                                                                       heatpump_max_heat=heatpump_max_heat,
                                                                       energy_shallow_cap=[10] * n_agents,  # TODO
                                                                       energy_deep_cap=[10] * n_agents,  # TODO
                                                                       heat_rate_shallow=[0] * n_agents,  # TODO
                                                                       Kval=[0] * n_agents,  # TODO
                                                                       Kloss_shallow=[0] * n_agents,  # TODO
                                                                       Kloss_deep=[0] * n_agents,  # TODO
                                                                       elec_consumption=elec_demand_df,
                                                                       hot_water_heatdem=high_heat_demand_df,
                                                                       space_heating_heatdem=low_heat_demand_df,
                                                                       cold_consumption=cooling_demand_df,
                                                                       pv_production=elec_supply_df,
                                                                       battery_efficiency=area_info['BatteryEfficiency'],
                                                                       max_elec_transfer_between_agents=area_info['InterAgentElectricityTransferCapacity'],
                                                                       max_elec_transfer_to_external=grid_agents[Resource.ELECTRICITY].max_transfer_per_hour,
                                                                       max_heat_transfer_between_agents=area_info['InterAgentHeatTransferCapacity'],
                                                                       max_heat_transfer_to_external=grid_agents[Resource.HEATING].max_transfer_per_hour,
                                                                       chiller_COP=area_info['COPCompChiller'],
                                                                       thermalstorage_capacity=10.0,  # TODO
                                                                       thermalstorage_charge_rate=1.0,  # TODO
                                                                       thermalstorage_efficiency=1.0,  # TODO
                                                                       trading_horizon=area_info['TradingHorizon']
                                                                       )

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


def build_supply_and_demand_dfs(agents: List[BlockAgent], start_datetime: datetime.datetime, trading_horizon: int) -> \
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
    transfers: List[Trade] = []
    for hour in optimized_model.T:
        add_external_trade(transfers, bought_from_external_name, hour, optimized_model, sold_to_external_name,
                           start_datetime, grid_agent_guid, resource)
        for i_agent in optimized_model.I:
            add_agent_trade(transfers, bought_internal_name, sold_internal_name, hour, i_agent, optimized_model,
                            start_datetime, resource, agent_guids)
    return transfers


def add_agent_trade(trade_list: List[Trade], bought_internal_name: str, sold_internal_name: str, hour: int,
                    i_agent: int, optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                    resource: Resource, agent_guids: List[str]):
    quantity = pyo.value(getattr(optimized_model, bought_internal_name)[i_agent, hour]
                         - getattr(optimized_model, sold_internal_name)[i_agent, hour])
    agent_name = agent_guids[i_agent]
    if quantity != 0:
        trade_list.append(Trade(period=start_datetime + datetime.timedelta(hours=hour),
                                action=Action.BUY if quantity > 0 else Action.SELL, resource=resource,
                                quantity=abs(quantity), price=np.nan, source=agent_name, by_external=False,
                                market=Market.LOCAL))


def add_external_trade(trade_list: List[Trade], bought_from_external_name: str, hour: int,
                       optimized_model: pyo.ConcreteModel, sold_to_external_name: str,
                       start_datetime: datetime.datetime, grid_agent_guid: str, resource: Resource):
    external_quantity = pyo.value(getattr(optimized_model, sold_to_external_name)[hour]
                                  - getattr(optimized_model, bought_from_external_name)[hour])
    if external_quantity != 0:
        trade_list.append(Trade(period=start_datetime + datetime.timedelta(hours=hour),
                                action=Action.BUY if external_quantity > 0 else Action.SELL, resource=resource,
                                quantity=abs(external_quantity), price=np.nan, source=grid_agent_guid, by_external=True,
                                market=Market.LOCAL))


def add_value_per_agent_to_dict(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                                dict_to_add_to: Dict[str, Dict[datetime.datetime, Any]],
                                variable_name: str, agent_guids: List[str]):
    """
    Example variable names: "Hhp" for heat pump production, "SOCBES" for state of charge of battery storage.
    Adds to a nested dict where agent GUID is the first key, the period the second.
    """
    for hour in optimized_model.T:
        for i_agent in optimized_model.I:
            quantity = pyo.value(getattr(optimized_model, variable_name)[i_agent, hour])
            period = start_datetime + datetime.timedelta(hours=hour)
            add_to_nested_dict(dict_to_add_to, agent_guids[i_agent], period, quantity)


def get_value_per_agent(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                        variable_name: str, agent_guids: List[str]) -> Dict[str, Dict[datetime.datetime, Any]]:
    """
    Example variable names: "Hhp" for heat pump production, "SOCBES" for state of charge of battery storage.
    Returns a nested dict where agent GUID is the first key, the period the second.
    """
    dict_to_add_to: Dict[str, Dict[datetime.datetime, Any]] = {}
    for hour in optimized_model.T:
        for i_agent in optimized_model.I:
            quantity = pyo.value(getattr(optimized_model, variable_name)[i_agent, hour])
            period = start_datetime + datetime.timedelta(hours=hour)
            add_to_nested_dict(dict_to_add_to, agent_guids[i_agent], period, quantity)
    return dict_to_add_to
