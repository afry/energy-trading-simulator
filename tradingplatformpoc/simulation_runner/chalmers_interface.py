import datetime
import logging
from typing import Any, Callable, Dict, List, Tuple, Union

import numpy as np

import pandas as pd

import pyomo.environ as pyo
from pyomo.core.base.param import IndexedParam, ScalarParam
from pyomo.opt import OptSolver, SolverResults, TerminationCondition
from pyomo.util.infeasible import log_infeasible_constraints

from tradingplatformpoc import constants
from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.trade import Action, Market, Resource, Trade
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.price.iprice import IPrice
from tradingplatformpoc.simulation_runner import CEMS_function
from tradingplatformpoc.trading_platform_utils import add_to_nested_dict

VERY_SMALL_NUMBER = 0.000001  # to avoid trades with quantity 1e-7, for example
DECIMALS_TO_ROUND_TO = 6  # To avoid saving for example storage levels of -1e-8

logger = logging.getLogger(__name__)


"""
Here we keep methods that do either
 1. Construct inputs to Chalmers' solve_model function, from agent data
 2. Translate the optimized pyo.ConcreteModel back to our domain (Trades, metadata etc)
"""


class ChalmersOutputs:
    trades: List[Trade]
    # (agent_guid, (period, level))
    battery_storage_levels: Dict[str, Dict[datetime.datetime, float]]
    acc_tank_levels: Dict[str, Dict[datetime.datetime, float]]
    shallow_storage_rel: Dict[str, Dict[datetime.datetime, float]]
    deep_storage_rel: Dict[str, Dict[datetime.datetime, float]]
    shallow_storage_abs: Dict[str, Dict[datetime.datetime, float]]
    deep_storage_abs: Dict[str, Dict[datetime.datetime, float]]
    shallow_loss: Dict[str, Dict[datetime.datetime, float]]
    deep_loss: Dict[str, Dict[datetime.datetime, float]]
    shallow_charge: Dict[str, Dict[datetime.datetime, float]]
    shallow_discharge: Dict[str, Dict[datetime.datetime, float]]
    bites_flow: Dict[str, Dict[datetime.datetime, float]]
    hp_high_prod: Dict[str, Dict[datetime.datetime, float]]
    hp_low_prod: Dict[str, Dict[datetime.datetime, float]]
    heat_dump: Dict[datetime.datetime, float]

    def __init__(self, trades: List[Trade],
                 battery_storage_levels: Dict[str, Dict[datetime.datetime, float]],
                 acc_tank_levels: Dict[str, Dict[datetime.datetime, float]],
                 shallow_storage_rel: Dict[str, Dict[datetime.datetime, float]],
                 deep_storage_rel: Dict[str, Dict[datetime.datetime, float]],
                 shallow_storage_abs: Dict[str, Dict[datetime.datetime, float]],
                 deep_storage_abs: Dict[str, Dict[datetime.datetime, float]],
                 shallow_loss: Dict[str, Dict[datetime.datetime, float]],
                 deep_loss: Dict[str, Dict[datetime.datetime, float]],
                 shallow_charge: Dict[str, Dict[datetime.datetime, float]],
                 shallow_discharge: Dict[str, Dict[datetime.datetime, float]],
                 bites_flow: Dict[str, Dict[datetime.datetime, float]],
                 hp_high_prod: Dict[str, Dict[datetime.datetime, float]],
                 hp_low_prod: Dict[str, Dict[datetime.datetime, float]],
                 heat_dump: Dict[datetime.datetime, float]):
        self.trades = trades
        self.battery_storage_levels = battery_storage_levels
        self.acc_tank_levels = acc_tank_levels
        self.shallow_storage_rel = shallow_storage_rel
        self.deep_storage_rel = deep_storage_rel
        self.shallow_storage_abs = shallow_storage_abs
        self.deep_storage_abs = deep_storage_abs
        self.shallow_loss = shallow_loss
        self.deep_loss = deep_loss
        self.shallow_charge = shallow_charge
        self.shallow_discharge = shallow_discharge
        self.bites_flow = bites_flow
        self.hp_high_prod = hp_high_prod
        self.hp_low_prod = hp_low_prod
        self.heat_dump = heat_dump


def optimize(solver: OptSolver, agents: List[IAgent], grid_agents: Dict[Resource, GridAgent], area_info: Dict[str, Any],
             start_datetime: datetime.datetime, elec_pricing: ElectricityPrice, heat_pricing: HeatingPrice,
             shallow_storage_start_dict: Dict[str, float], deep_storage_start_dict: Dict[str, float]) \
        -> ChalmersOutputs:
    block_agents: List[BlockAgent] = [agent for agent in agents if isinstance(agent, BlockAgent)]
    agent_guids = [agent.guid for agent in agents]
    # The order specified in "agents" will be used throughout
    trading_horizon = area_info['TradingHorizon']

    elec_demand_df, elec_supply_df, high_heat_demand_df, high_heat_supply_df, \
        low_heat_demand_df, low_heat_supply_df, cooling_demand_df, cooling_supply_df = \
        build_supply_and_demand_dfs(block_agents, start_datetime, trading_horizon)

    battery_capacities = [agent.battery.max_capacity_kwh for agent in block_agents]
    battery_max_charge = [agent.battery.charge_limit_kwh for agent in block_agents]
    battery_max_discharge = [agent.battery.discharge_limit_kwh for agent in block_agents]
    acc_tank_volumes = [agent.acc_tank_volume for agent in block_agents]
    heatpump_max_power = [agent.heat_pump_max_input for agent in block_agents]
    heatpump_max_heat = [agent.heat_pump_max_output for agent in block_agents]
    booster_max_power = [agent.booster_pump_max_input for agent in block_agents]
    booster_max_heat = [agent.booster_pump_max_output for agent in block_agents]
    gross_floor_area = [agent.digital_twin.gross_floor_area for agent in block_agents]
    shallow_storage_start = [(shallow_storage_start_dict[agent] if agent in shallow_storage_start_dict.keys() else 0.0)
                             for agent in agent_guids]
    deep_storage_start = [(deep_storage_start_dict[agent] if agent in shallow_storage_start_dict.keys() else 0.0)
                          for agent in agent_guids]

    retail_prices: pd.Series = elec_pricing.get_exact_retail_prices(start_datetime, trading_horizon, True)
    wholesale_prices: pd.Series = elec_pricing.get_exact_wholesale_prices(start_datetime, trading_horizon)
    elec_retail_prices = retail_prices.reset_index(drop=True)
    elec_wholesale_prices = wholesale_prices.reset_index(drop=True)
    heat_retail_price = heat_pricing.get_estimated_retail_price(start_datetime, True)

    n_agents = len(block_agents)
    optimized_model, results = CEMS_function.solve_model(
        solver=solver,
        summer_mode=should_use_summer_mode(start_datetime),
        n_agents=n_agents,
        external_elec_buy_price=elec_retail_prices,
        external_elec_sell_price=elec_wholesale_prices,
        external_heat_buy_price=heat_retail_price,
        battery_capacity=battery_capacities,
        battery_charge_rate=battery_max_charge,
        battery_discharge_rate=battery_max_discharge,
        SOCBES0=[area_info['StorageEndChargeLevel']] * n_agents,
        heatpump_COP=[area_info['COPHeatPumps']] * n_agents,
        heatpump_max_power=heatpump_max_power,
        heatpump_max_heat=heatpump_max_heat,
        booster_heatpump_COP=[area_info['COPBoosterPumps']] * n_agents,
        booster_heatpump_max_power=booster_max_power,
        booster_heatpump_max_heat=booster_max_heat,
        build_area=gross_floor_area,
        SOCTES0=[area_info['StorageEndChargeLevel']] * n_agents,
        thermalstorage_max_temp=[65] * n_agents,  # TODO ?
        thermalstorage_volume=acc_tank_volumes,
        BITES_Eshallow0=shallow_storage_start,
        BITES_Edeep0=deep_storage_start,
        elec_consumption=elec_demand_df,
        hot_water_heatdem=high_heat_demand_df,
        space_heating_heatdem=low_heat_demand_df,
        cold_consumption=cooling_demand_df,
        pv_production=elec_supply_df,
        excess_heat=low_heat_supply_df,
        battery_efficiency=area_info['BatteryEfficiency'],
        max_elec_transfer_between_agents=area_info['InterAgentElectricityTransferCapacity'],
        max_elec_transfer_to_external=grid_agents[Resource.ELECTRICITY].max_transfer_per_hour,
        max_heat_transfer_between_agents=area_info['InterAgentHeatTransferCapacity'],
        max_heat_transfer_to_external=grid_agents[Resource.HIGH_TEMP_HEAT].max_transfer_per_hour,
        chiller_COP=area_info['COPCompChiller'],
        heat_trans_loss=area_info['HeatTransferLoss'],
        trading_horizon=trading_horizon
    )

    if results.solver.termination_condition != TerminationCondition.optimal:
        # Raise error here?
        logger.error('For period {}, the solver did not find an optimal solution. Solver status: {}'.format(
            start_datetime, results.solver.termination_condition))
        log_infeasible_constraints(optimized_model)

    elec_grid_agent_guid = grid_agents[Resource.ELECTRICITY].guid
    heat_grid_agent_guid = grid_agents[Resource.HIGH_TEMP_HEAT].guid
    return extract_outputs(optimized_model, results, start_datetime,
                           elec_grid_agent_guid, heat_grid_agent_guid,
                           elec_pricing, heat_pricing,
                           agent_guids)


def should_use_summer_mode(start_datetime: datetime.datetime) -> bool:
    """In the 'summer mode', heat trades within the LEC are of LOW_TEMP_HEAT, instead of HIGH_TEMP_HEAT."""
    return start_datetime.month in constants.SUMMER_MODE_MONTHS


def extract_outputs(optimized_model: pyo.ConcreteModel,
                    solver_results: SolverResults,
                    start_datetime: datetime.datetime,
                    elec_grid_agent_guid: str,
                    heat_grid_agent_guid: str,
                    electricity_price_data: ElectricityPrice,
                    heating_price_data: HeatingPrice,
                    agent_guids: List[str]) -> ChalmersOutputs:
    elec_trades = get_power_transfers(optimized_model, start_datetime, elec_grid_agent_guid, agent_guids,
                                      electricity_price_data)
    heat_trades = get_heat_transfers(optimized_model, start_datetime, heat_grid_agent_guid, agent_guids,
                                     heating_price_data)
    battery_storage_levels = get_value_per_agent(optimized_model, start_datetime, 'SOCBES', agent_guids,
                                                 lambda i: optimized_model.Emax_BES[i] > 0)
    acc_tank_levels = get_value_per_agent(optimized_model, start_datetime, 'SOCTES', agent_guids,
                                          lambda i: optimized_model.kwh_per_deg[i] > 0)
    shallow_storage_rel = get_value_per_agent(optimized_model, start_datetime, 'Energy_shallow', agent_guids,
                                              lambda i: optimized_model.Energy_shallow_cap[i] > 0,
                                              lambda i: optimized_model.Energy_shallow_cap[i])
    deep_storage_rel = get_value_per_agent(optimized_model, start_datetime, 'Energy_deep', agent_guids,
                                           lambda i: optimized_model.Energy_deep_cap[i] > 0,
                                           lambda i: optimized_model.Energy_deep_cap[i])
    shallow_storage_abs = get_value_per_agent(optimized_model, start_datetime, 'Energy_shallow', agent_guids,
                                              lambda i: optimized_model.Energy_shallow_cap[i] > 0)
    deep_storage_abs = get_value_per_agent(optimized_model, start_datetime, 'Energy_deep', agent_guids,
                                           lambda i: optimized_model.Energy_deep_cap[i] > 0)
    shallow_loss = get_value_per_agent(optimized_model, start_datetime, 'Loss_shallow', agent_guids,
                                       lambda i: optimized_model.Energy_shallow_cap[i] > 0)
    deep_loss = get_value_per_agent(optimized_model, start_datetime, 'Loss_deep', agent_guids,
                                    lambda i: optimized_model.Energy_deep_cap[i] > 0)
    shallow_charge = get_value_per_agent(optimized_model, start_datetime, 'Hcha_shallow', agent_guids,
                                         lambda i: optimized_model.Energy_shallow_cap[i] > 0)
    shallow_discharge = get_value_per_agent(optimized_model, start_datetime, 'Hdis_shallow', agent_guids,
                                            lambda i: optimized_model.Energy_shallow_cap[i] > 0)
    bites_flow = get_value_per_agent(optimized_model, start_datetime, 'Flow', agent_guids,
                                     lambda i: optimized_model.Energy_deep_cap[i] > 0)
    if should_use_summer_mode(start_datetime):
        hp_low_prod = get_value_per_agent(optimized_model, start_datetime, 'Hhp', agent_guids,
                                          lambda i: optimized_model.Phpmax[i] > 0)
        hp_high_prod = get_value_per_agent(optimized_model, start_datetime, 'HhpB', agent_guids,
                                           lambda i: optimized_model.PhpBmax[i] > 0)
    else:
        hp_high_prod = get_value_per_agent(optimized_model, start_datetime, 'Hhp', agent_guids,
                                           lambda i: optimized_model.Phpmax[i] > 0)
        hp_low_prod = {}
    heat_dump = get_value_per_period(optimized_model, start_datetime, 'heat_dump')
    return ChalmersOutputs(elec_trades + heat_trades,
                           battery_storage_levels,
                           acc_tank_levels,
                           shallow_storage_rel,
                           deep_storage_rel,
                           shallow_storage_abs,
                           deep_storage_abs,
                           shallow_loss,
                           deep_loss,
                           shallow_charge,
                           shallow_discharge,
                           bites_flow,
                           hp_high_prod,
                           hp_low_prod,
                           heat_dump)


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
                        agent_guids: List[str], resource_price_data: ElectricityPrice) -> List[Trade]:
    # For example: Pbuy_market is how much the LEC bought from the external grid operator
    inter_agent_trades = get_agent_transfers(optimized_model, start_datetime,
                                             sold_internal_name='Psell_grid', bought_internal_name='Pbuy_grid',
                                             resource=Resource.ELECTRICITY, agent_guids=agent_guids)
    external_trades = get_external_transfers(optimized_model, start_datetime,
                                             sold_to_external_name='Psell_market',
                                             bought_from_external_name='Pbuy_market',
                                             retail_price_name='price_buy', wholesale_price_name='price_sell',
                                             resource=Resource.ELECTRICITY, grid_agent_guid=grid_agent_guid,
                                             resource_price_data=resource_price_data)
    return inter_agent_trades + external_trades


def get_heat_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime, grid_agent_guid: str,
                       agent_guids: List[str], resource_price_data: HeatingPrice) -> List[Trade]:
    resource = Resource.LOW_TEMP_HEAT if should_use_summer_mode(start_datetime) else Resource.HIGH_TEMP_HEAT
    inter_agent_trades = get_agent_transfers(optimized_model, start_datetime,
                                             sold_internal_name='Hsell_grid', bought_internal_name='Hbuy_grid',
                                             resource=resource, agent_guids=agent_guids)
    external_trades = get_external_transfers(optimized_model, start_datetime,
                                             sold_to_external_name='NA', bought_from_external_name='Hbuy_market',
                                             retail_price_name='Hprice_energy', wholesale_price_name='NA',
                                             resource=Resource.HIGH_TEMP_HEAT, grid_agent_guid=grid_agent_guid,
                                             resource_price_data=resource_price_data)
    return inter_agent_trades + external_trades


def get_external_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                           sold_to_external_name: str, bought_from_external_name: str,
                           retail_price_name: str, wholesale_price_name: str,
                           resource: Resource, grid_agent_guid: str, resource_price_data: IPrice) -> List[Trade]:
    transfers: List[Trade] = []
    for hour in optimized_model.T:
        add_external_trade(transfers, bought_from_external_name, hour, optimized_model, sold_to_external_name,
                           retail_price_name, wholesale_price_name, start_datetime, grid_agent_guid, resource,
                           resource_price_data)
    return transfers


def get_agent_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                        sold_internal_name: str, bought_internal_name: str,
                        resource: Resource, agent_guids: List[str]) -> List[Trade]:
    transfers: List[Trade] = []
    for hour in optimized_model.T:
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
    if quantity > VERY_SMALL_NUMBER or quantity < -VERY_SMALL_NUMBER:
        trade_list.append(Trade(period=start_datetime + datetime.timedelta(hours=hour),
                                action=Action.BUY if quantity > 0 else Action.SELL, resource=resource,
                                quantity=abs(quantity), price=np.nan, source=agent_name, by_external=False,
                                market=Market.LOCAL))


def add_external_trade(trade_list: List[Trade], bought_from_external_name: str, hour: int,
                       optimized_model: pyo.ConcreteModel, sold_to_external_name: str, retail_price_name: str,
                       wholesale_price_name: str, start_datetime: datetime.datetime, grid_agent_guid: str,
                       resource: Resource, resource_price_data: IPrice):
    external_quantity = pyo.value(get_variable_value_or_else(optimized_model, sold_to_external_name, hour)
                                  - get_variable_value_or_else(optimized_model, bought_from_external_name, hour))
    period = start_datetime + datetime.timedelta(hours=hour)
    if external_quantity > VERY_SMALL_NUMBER:
        wholesale_prices = getattr(optimized_model, wholesale_price_name)
        price = get_value_from_param(wholesale_prices, hour)
        trade_list.append(Trade(period=period,
                                action=Action.BUY, resource=resource, quantity=external_quantity,
                                price=price, source=grid_agent_guid, by_external=True, market=Market.LOCAL))
    elif external_quantity < -VERY_SMALL_NUMBER:
        retail_prices = getattr(optimized_model, retail_price_name)
        price = get_value_from_param(retail_prices, hour)
        trade_list.append(Trade(period=period,
                                action=Action.SELL, resource=resource, quantity=-external_quantity,
                                price=price, source=grid_agent_guid, by_external=True, market=Market.LOCAL,
                                tax_paid=resource_price_data.tax))
        if isinstance(resource_price_data, HeatingPrice):
            resource_price_data.add_external_heating_sell(period, -external_quantity)


def get_value_from_param(maybe_indexed_param: Union[IndexedParam, ScalarParam], index: int) -> float:
    """If maybe_indexed_param is indexed, gets the 'index':th value. If it is a scalar, gets its value."""
    if isinstance(maybe_indexed_param, IndexedParam):
        return maybe_indexed_param[index]
    elif isinstance(maybe_indexed_param, ScalarParam):
        return maybe_indexed_param.value
    raise RuntimeError('Unsupported type: {}'.format(type(maybe_indexed_param)))


def get_variable_value_or_else(optimized_model: pyo.ConcreteModel, variable_name: str, index: int,
                               if_not_exists: float = 0.0) -> float:
    if hasattr(optimized_model, variable_name):
        return getattr(optimized_model, variable_name)[index]
    return if_not_exists


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
                        variable_name: str, agent_guids: List[str],
                        should_add_for_agent: Callable[[int], bool],
                        divide_by: Callable[[int], float] = lambda i: 1.0) \
        -> Dict[str, Dict[datetime.datetime, Any]]:
    """
    Example variable names: "Hhp" for heat pump production, "SOCBES" for state of charge of battery storage.
    Returns a nested dict where agent GUID is the first key, the period the second.
    Will only add values for which "should_add_for_agent(agent_index)" is True. This can be used to ensure that battery
    charge state is only added for agents that actually have a battery.
    If "divide_by" is specified, all quantities will be divided by "divide_by(agent_index)". Can be used to translate
    energy quantities to % of max, for example.
    """
    dict_to_add_to: Dict[str, Dict[datetime.datetime, Any]] = {}
    for hour in optimized_model.T:
        period = start_datetime + datetime.timedelta(hours=hour)
        for i_agent in optimized_model.I:
            if should_add_for_agent(i_agent):
                quantity = pyo.value(getattr(optimized_model, variable_name)[i_agent, hour])
                value = round(quantity / divide_by(i_agent), DECIMALS_TO_ROUND_TO)
                add_to_nested_dict(dict_to_add_to, agent_guids[i_agent], period, value)
    return dict_to_add_to


def get_value_per_period(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime, variable_name: str) \
        -> Dict[datetime.datetime, Any]:
    """
    Example variable names: "heat_dump" for heat reservoir.
    """
    dict_to_add_to: Dict[datetime.datetime, Any] = {}
    for hour in optimized_model.T:
        period = start_datetime + datetime.timedelta(hours=hour)
        quantity = pyo.value(getattr(optimized_model, variable_name)[hour])
        dict_to_add_to[period] = round(quantity, DECIMALS_TO_ROUND_TO)
    return dict_to_add_to
