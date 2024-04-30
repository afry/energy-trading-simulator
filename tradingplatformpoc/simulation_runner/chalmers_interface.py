import datetime
import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np

import pandas as pd

import pyomo.environ as pyo
from pyomo.core.base.param import IndexedParam, ScalarParam
from pyomo.core.base.var import IndexedVar
from pyomo.opt import OptSolver, SolverResults, TerminationCondition
from pyomo.util.infeasible import find_infeasible_constraints, log_infeasible_constraints

from tradingplatformpoc import constants
from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.trade import Action, Market, Resource, Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.price.iprice import IPrice
from tradingplatformpoc.simulation_runner.chalmers import AgentEMS, CEMS_function
from tradingplatformpoc.simulation_runner.chalmers.domain import CEMSError
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
    # (TradeMetadataKey, agent_guid, (period, level)))
    metadata_per_agent_and_period: Dict[TradeMetadataKey, Dict[str, Dict[datetime.datetime, float]]]
    # Data which isn't agent-individual: (TradeMetadataKey, (period, level))
    metadata_per_period: Dict[TradeMetadataKey, Dict[datetime.datetime, float]]

    def __init__(self, trades: List[Trade],
                 metadata_per_agent_and_period: Dict[TradeMetadataKey, Dict[str, Dict[datetime.datetime, float]]],
                 metadata_per_period: Dict[TradeMetadataKey, Dict[datetime.datetime, float]]):
        self.trades = trades
        self.metadata_per_agent_and_period = metadata_per_agent_and_period
        self.metadata_per_period = metadata_per_period


class InfeasibilityError(CEMSError):
    agent_names: List[str]
    horizon_start: datetime.datetime
    horizon_end: datetime.datetime
    constraints: Set[str]

    def __init__(self, message: str, agent_names: List[str], hour_indices: List[int],
                 horizon_start: datetime.datetime, horizon_end: datetime.datetime, constraints: Set[str]):
        super().__init__(message, [], hour_indices)
        self.agent_names = agent_names
        self.horizon_start = horizon_start
        self.horizon_end = horizon_end
        self.constraints = constraints


def optimize(solver: OptSolver, agents: List[IAgent], grid_agents: Dict[Resource, GridAgent], area_info: Dict[str, Any],
             start_datetime: datetime.datetime, elec_pricing: ElectricityPrice, heat_pricing: HeatingPrice,
             shallow_storage_start_dict: Dict[str, float], deep_storage_start_dict: Dict[str, float]) \
        -> ChalmersOutputs:
    block_agents: List[BlockAgent] = [agent for agent in agents if isinstance(agent, BlockAgent)]
    elec_grid_agent_guid = grid_agents[Resource.ELECTRICITY].guid
    heat_grid_agent_guid = grid_agents[Resource.HIGH_TEMP_HEAT].guid
    agent_guids = [agent.guid for agent in block_agents]
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
    atemp_for_bites = [agent.digital_twin.atemp * agent.frac_for_bites for agent in block_agents]
    hp_produce_cooling = [agent.digital_twin.hp_produce_cooling for agent in block_agents]
    shallow_storage_start = [(shallow_storage_start_dict[agent] if agent in shallow_storage_start_dict.keys() else 0.0)
                             for agent in agent_guids]
    deep_storage_start = [(deep_storage_start_dict[agent] if agent in shallow_storage_start_dict.keys() else 0.0)
                          for agent in agent_guids]

    retail_prices: pd.Series = elec_pricing.get_exact_retail_prices(start_datetime, trading_horizon, True)
    wholesale_prices: pd.Series = elec_pricing.get_exact_wholesale_prices(start_datetime, trading_horizon)
    nordpool_prices: pd.Series = elec_pricing.get_nordpool_price_for_periods(start_datetime, trading_horizon)
    elec_retail_prices = retail_prices.reset_index(drop=True)
    elec_wholesale_prices = wholesale_prices.reset_index(drop=True)
    nordpool_prices = nordpool_prices.reset_index(drop=True)
    heat_retail_price = heat_pricing.get_estimated_retail_price(start_datetime, True)

    n_agents = len(block_agents)
    summer_mode = should_use_summer_mode(start_datetime)
    heat_pump_cop = area_info['COPHeatPumpsLowTemp'] if summer_mode else area_info['COPHeatPumpsHighTemp']
    try:
        if area_info['LocalMarketEnabled']:
            optimized_model, results = CEMS_function.solve_model(
                solver=solver,
                summer_mode=summer_mode,
                month=start_datetime.month,
                n_agents=n_agents,
                external_elec_buy_price=elec_retail_prices,
                external_elec_sell_price=elec_wholesale_prices,
                external_heat_buy_price=heat_retail_price,
                battery_capacity=battery_capacities,
                battery_charge_rate=battery_max_charge,
                battery_discharge_rate=battery_max_discharge,
                SOCBES0=[area_info['StorageEndChargeLevel']] * n_agents,
                heatpump_COP=[heat_pump_cop] * n_agents,
                heatpump_max_power=heatpump_max_power,
                heatpump_max_heat=heatpump_max_heat,
                HP_Cproduct_active=hp_produce_cooling,
                borehole=hp_produce_cooling,
                booster_heatpump_COP=[area_info['COPBoosterPumps']] * n_agents,
                booster_heatpump_max_power=booster_max_power,
                booster_heatpump_max_heat=booster_max_heat,
                build_area=atemp_for_bites,
                SOCTES0=[area_info['StorageEndChargeLevel']] * n_agents,
                thermalstorage_max_temp=[constants.ACC_TANK_TEMPERATURE] * n_agents,
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
                thermalstorage_efficiency=area_info['AccTankEfficiency'],
                max_elec_transfer_between_agents=area_info['InterAgentElectricityTransferCapacity'],
                max_elec_transfer_to_external=grid_agents[Resource.ELECTRICITY].max_transfer_per_hour,
                max_heat_transfer_between_agents=area_info['InterAgentHeatTransferCapacity'],
                max_heat_transfer_to_external=grid_agents[Resource.HIGH_TEMP_HEAT].max_transfer_per_hour,
                chiller_COP=area_info['CompChillerCOP'],
                Pccmax=area_info['CompChillerMaxInput'],
                cold_trans_loss=area_info['CoolingTransferLoss'],
                heat_trans_loss=area_info['HeatTransferLoss'],
                trading_horizon=trading_horizon
            )
            handle_infeasibility(optimized_model, results, start_datetime, trading_horizon, [])
            return extract_outputs_for_lec(optimized_model, start_datetime,
                                           elec_grid_agent_guid, heat_grid_agent_guid,
                                           elec_pricing, heat_pricing,
                                           agent_guids)
        else:
            all_trades: List[Trade] = []
            all_metadata: Dict[str, Dict[TradeMetadataKey, Dict[datetime.datetime, float]]] = {}
            for i_agent in range(len(block_agents)):
                optimized_model, results = AgentEMS.solve_model(
                    solver=solver,
                    month=start_datetime.month,
                    agent=i_agent,
                    external_elec_buy_price=nordpool_prices,
                    external_elec_sell_price=nordpool_prices,
                    external_heat_buy_price=heat_retail_price,
                    battery_capacity=battery_capacities[i_agent],
                    battery_charge_rate=battery_max_charge[i_agent],
                    battery_discharge_rate=battery_max_discharge[i_agent],
                    SOCBES0=area_info['StorageEndChargeLevel'],
                    heatpump_COP=heat_pump_cop,
                    heatpump_max_power=heatpump_max_power[i_agent],
                    heatpump_max_heat=heatpump_max_heat[i_agent],
                    HP_Cproduct_active=hp_produce_cooling[i_agent],
                    borehole=hp_produce_cooling[i_agent],
                    build_area=atemp_for_bites[i_agent],
                    SOCTES0=area_info['StorageEndChargeLevel'],
                    thermalstorage_max_temp=constants.ACC_TANK_TEMPERATURE,
                    thermalstorage_volume=acc_tank_volumes[i_agent],
                    BITES_Eshallow0=shallow_storage_start[i_agent],
                    BITES_Edeep0=deep_storage_start[i_agent],
                    elec_consumption=elec_demand_df.iloc[i_agent, :],
                    hot_water_heatdem=high_heat_demand_df.iloc[i_agent, :],
                    space_heating_heatdem=low_heat_demand_df.iloc[i_agent, :],
                    cold_consumption=cooling_demand_df.iloc[i_agent, :],
                    pv_production=elec_supply_df.iloc[i_agent, :],
                    excess_heat=low_heat_supply_df.iloc[i_agent, :],
                    battery_efficiency=area_info['BatteryEfficiency'],
                    thermalstorage_efficiency=area_info['AccTankEfficiency'],
                    max_elec_transfer_to_external=grid_agents[Resource.ELECTRICITY].max_transfer_per_hour,
                    max_heat_transfer_to_external=grid_agents[Resource.HIGH_TEMP_HEAT].max_transfer_per_hour,
                    heat_trans_loss=area_info['HeatTransferLoss'],
                    trading_horizon=trading_horizon,
                    elec_tax_fee=elec_pricing.tax,
                    elec_trans_fee=elec_pricing.transmission_fee,
                    elec_peak_load_fee=elec_pricing.effect_fee,
                    heat_peak_load_fee=heat_pricing.effect_fee,
                    incentive_fee=elec_pricing.wholesale_offset,
                    hist_monthly_elec_peak_load=10000.0,  # TODO
                    hist_monthly_heat_peak_energy=10000.0,  # TODO
                )
                handle_infeasibility(optimized_model, results, start_datetime, trading_horizon,
                                     [block_agents[i_agent].guid])
                trades, metadata = extract_outputs_for_agent(optimized_model, start_datetime,
                                                             elec_grid_agent_guid, heat_grid_agent_guid,
                                                             elec_pricing, heat_pricing,
                                                             agent_guids[i_agent])
                all_trades.extend(trades)
                all_metadata[agent_guids[i_agent]] = metadata

        metadata_per_agent_and_period = flip_dict_keys(all_metadata)
        metadata_per_period: Dict[TradeMetadataKey, Dict[datetime.datetime, float]] = {
            TradeMetadataKey.HEAT_DUMP: sum_for_all_agents(metadata_per_agent_and_period[TradeMetadataKey.HEAT_DUMP]),
            TradeMetadataKey.COOL_DUMP: sum_for_all_agents(metadata_per_agent_and_period[TradeMetadataKey.COOL_DUMP])
        }
        return ChalmersOutputs(all_trades, metadata_per_agent_and_period, metadata_per_period)
    except CEMSError as e:
        raise InfeasibilityError(message=e.message,
                                 agent_names=[agent_guids[i] for i in e.agent_indices],
                                 hour_indices=e.hour_indices,
                                 horizon_start=start_datetime,
                                 horizon_end=start_datetime + datetime.timedelta(hours=trading_horizon),
                                 constraints=set())


def sum_for_all_agents(dict_per_agent_and_period: Dict[str, Dict[datetime.datetime, float]]) \
        -> Dict[datetime.datetime, float]:
    return {date: sum(inner_dict[date] for inner_dict in dict_per_agent_and_period.values() if date in inner_dict)
            for date in set(date for inner_dict in dict_per_agent_and_period.values() for date in inner_dict)}


def flip_dict_keys(all_metadata: Dict[str, Dict[TradeMetadataKey, Dict[datetime.datetime, float]]]) \
        -> Dict[TradeMetadataKey, Dict[str, Dict[datetime.datetime, float]]]:
    metadata_per_agent: Dict[TradeMetadataKey, Dict[str, Dict[datetime.datetime, float]]] = {}
    for agent_name, inner_dict in all_metadata.items():
        for metadata_key, date_value_dict in inner_dict.items():
            if metadata_key not in metadata_per_agent:
                metadata_per_agent[metadata_key] = {}
            metadata_per_agent[metadata_key][agent_name] = date_value_dict
    return metadata_per_agent


def handle_infeasibility(optimized_model: pyo.ConcreteModel, results: SolverResults, start_datetime: datetime.datetime,
                         trading_horizon: int, agent_names: List[str]):
    """If the solver exits with infeasibility, log this, and raise an informative error."""
    if results.solver.termination_condition != TerminationCondition.optimal:
        constraint_names_no_index: Set[str] = set()
        for constraint, _body_value, _infeasible in find_infeasible_constraints(optimized_model):
            constraint_names_no_index.add(constraint.name.split('[')[0])
        log_infeasible_constraints(optimized_model)
        raise InfeasibilityError(message='Infeasible optimization problem',
                                 agent_names=agent_names,
                                 hour_indices=[],
                                 horizon_start=start_datetime,
                                 horizon_end=start_datetime + datetime.timedelta(hours=trading_horizon),
                                 constraints=constraint_names_no_index)


def should_use_summer_mode(start_datetime: datetime.datetime) -> bool:
    """In the 'summer mode', heat trades within the LEC are of LOW_TEMP_HEAT, instead of HIGH_TEMP_HEAT."""
    return start_datetime.month in constants.SUMMER_MODE_MONTHS


def extract_outputs_for_agent(optimized_model: pyo.ConcreteModel,
                              start_datetime: datetime.datetime,
                              elec_grid_agent_guid: str,
                              heat_grid_agent_guid: str,
                              electricity_price_data: ElectricityPrice,
                              heating_price_data: HeatingPrice,
                              agent_guid: str) -> \
        Tuple[List[Trade], Dict[TradeMetadataKey, Dict[datetime.datetime, float]]]:
    elec_trades = get_power_transfers(optimized_model, start_datetime, elec_grid_agent_guid, [agent_guid],
                                      electricity_price_data, local_market_enabled=False)
    heat_trades = get_heat_transfers(optimized_model, start_datetime, heat_grid_agent_guid, [agent_guid],
                                     heating_price_data, local_market_enabled=False)
    metadata = {
        TradeMetadataKey.BATTERY_LEVEL: get_value_per_period(optimized_model, start_datetime, 'SOCBES'),
        TradeMetadataKey.ACC_TANK_LEVEL: get_value_per_period(optimized_model, start_datetime, 'SOCTES'),
        TradeMetadataKey.SHALLOW_STORAGE_REL: get_value_per_period(optimized_model, start_datetime, 'Energy_shallow'),
        TradeMetadataKey.DEEP_STORAGE_REL: get_value_per_period(optimized_model, start_datetime, 'Energy_deep'),
        TradeMetadataKey.SHALLOW_STORAGE_ABS: get_value_per_period(optimized_model, start_datetime, 'Energy_shallow'),
        TradeMetadataKey.DEEP_STORAGE_ABS: get_value_per_period(optimized_model, start_datetime, 'Energy_deep'),
        TradeMetadataKey.SHALLOW_LOSS: get_value_per_period(optimized_model, start_datetime, 'Loss_shallow'),
        TradeMetadataKey.DEEP_LOSS: get_value_per_period(optimized_model, start_datetime, 'Loss_deep'),
        TradeMetadataKey.SHALLOW_CHARGE: get_value_per_period(optimized_model, start_datetime, 'Hcha_shallow'),
        TradeMetadataKey.FLOW_SHALLOW_TO_DEEP: get_value_per_period(optimized_model, start_datetime, 'Flow'),
        TradeMetadataKey.HP_COOL_PROD: get_value_per_period(optimized_model, start_datetime, 'Chp'),
        TradeMetadataKey.HP_HIGH_HEAT_PROD: get_value_per_period(optimized_model, start_datetime, 'Hhp'),
        # Heat dump and cool dump will have to be aggregated later
        TradeMetadataKey.HEAT_DUMP: get_value_per_period(optimized_model, start_datetime, 'heat_dump'),
        TradeMetadataKey.COOL_DUMP: get_value_per_period(optimized_model, start_datetime, 'cool_dump')
    }
    return elec_trades + heat_trades, metadata


def extract_outputs_for_lec(optimized_model: pyo.ConcreteModel,
                            start_datetime: datetime.datetime,
                            elec_grid_agent_guid: str,
                            heat_grid_agent_guid: str,
                            electricity_price_data: ElectricityPrice,
                            heating_price_data: HeatingPrice,
                            agent_guids: List[str]) -> ChalmersOutputs:
    elec_trades = get_power_transfers(optimized_model, start_datetime, elec_grid_agent_guid, agent_guids,
                                      electricity_price_data, local_market_enabled=True)
    heat_trades = get_heat_transfers(optimized_model, start_datetime, heat_grid_agent_guid, agent_guids,
                                     heating_price_data, local_market_enabled=True)
    cool_trades = get_cool_transfers(optimized_model, start_datetime, agent_guids)
    metadata_per_agent_and_period = {
        TradeMetadataKey.BATTERY_LEVEL: get_value_per_agent(optimized_model, start_datetime, 'SOCBES', agent_guids,
                                                            lambda i: optimized_model.Emax_BES[i] > 0),
        TradeMetadataKey.ACC_TANK_LEVEL: get_value_per_agent(optimized_model, start_datetime, 'SOCTES', agent_guids,
                                                             lambda i: optimized_model.kwh_per_deg[i] > 0),
        TradeMetadataKey.SHALLOW_STORAGE_REL: get_value_per_agent(optimized_model, start_datetime, 'Energy_shallow',
                                                                  agent_guids,
                                                                  lambda i: optimized_model.Energy_shallow_cap[i] > 0,
                                                                  lambda i: optimized_model.Energy_shallow_cap[i]),
        TradeMetadataKey.DEEP_STORAGE_REL: get_value_per_agent(optimized_model, start_datetime, 'Energy_deep',
                                                               agent_guids,
                                                               lambda i: optimized_model.Energy_deep_cap[i] > 0,
                                                               lambda i: optimized_model.Energy_deep_cap[i]),
        TradeMetadataKey.SHALLOW_STORAGE_ABS: get_value_per_agent(optimized_model, start_datetime, 'Energy_shallow',
                                                                  agent_guids,
                                                                  lambda i: optimized_model.Energy_shallow_cap[i] > 0),
        TradeMetadataKey.DEEP_STORAGE_ABS: get_value_per_agent(optimized_model, start_datetime, 'Energy_deep',
                                                               agent_guids,
                                                               lambda i: optimized_model.Energy_deep_cap[i] > 0),
        TradeMetadataKey.SHALLOW_LOSS: get_value_per_agent(optimized_model, start_datetime, 'Loss_shallow', agent_guids,
                                                           lambda i: optimized_model.Energy_shallow_cap[i] > 0),
        TradeMetadataKey.DEEP_LOSS: get_value_per_agent(optimized_model, start_datetime, 'Loss_deep', agent_guids,
                                                        lambda i: optimized_model.Energy_deep_cap[i] > 0),
        TradeMetadataKey.SHALLOW_CHARGE: get_value_per_agent(optimized_model, start_datetime, 'Hcha_shallow',
                                                             agent_guids,
                                                             lambda i: optimized_model.Energy_shallow_cap[i] > 0),
        TradeMetadataKey.FLOW_SHALLOW_TO_DEEP: get_value_per_agent(optimized_model, start_datetime, 'Flow', agent_guids,
                                                                   lambda i: optimized_model.Energy_deep_cap[i] > 0),
        TradeMetadataKey.HP_COOL_PROD: get_value_per_agent(optimized_model, start_datetime, 'Chp', agent_guids,
                                                           lambda i: optimized_model.Phpmax[i] > 0)
    }
    if should_use_summer_mode(start_datetime):
        metadata_per_agent_and_period[TradeMetadataKey.HP_LOW_HEAT_PROD] = \
            get_value_per_agent(optimized_model, start_datetime, 'Hhp', agent_guids,
                                lambda i: optimized_model.Phpmax[i] > 0)
        metadata_per_agent_and_period[TradeMetadataKey.HP_HIGH_HEAT_PROD] = \
            get_value_per_agent(optimized_model, start_datetime, 'HhpB', agent_guids,
                                lambda i: optimized_model.PhpBmax[i] > 0)
    else:
        metadata_per_agent_and_period[TradeMetadataKey.HP_LOW_HEAT_PROD] = {}
        metadata_per_agent_and_period[TradeMetadataKey.HP_HIGH_HEAT_PROD] = \
            get_value_per_agent(optimized_model, start_datetime, 'Hhp', agent_guids,
                                lambda i: optimized_model.Phpmax[i] > 0)

    # Build metadata per period (not agent-individual)
    metadata_per_period = {
        TradeMetadataKey.COOL_DUMP: get_value_per_period(optimized_model, start_datetime, 'cool_dump'),
        TradeMetadataKey.CM_COOL_PROD: get_value_per_period(optimized_model, start_datetime, 'Ccc'),
        TradeMetadataKey.CM_HEAT_PROD: get_value_per_period(optimized_model, start_datetime, 'Hcc'),
        TradeMetadataKey.CM_ELEC_CONS: get_value_per_period(optimized_model, start_datetime, 'Pcc')
    }
    heat_dump_per_agent = get_value_per_agent(optimized_model, start_datetime, 'heat_dump', agent_guids,
                                              lambda i: True)
    heat_dump_total = {dt: sum(inner_dict[dt] for inner_dict in heat_dump_per_agent.values() if dt in inner_dict)
                       for dt in set(key for inner_dict in heat_dump_per_agent.values() for key in inner_dict)}
    metadata_per_period[TradeMetadataKey.HEAT_DUMP] = heat_dump_total
    return ChalmersOutputs(elec_trades + heat_trades + cool_trades, metadata_per_agent_and_period, metadata_per_period)


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
                        agent_guids: List[str], resource_price_data: ElectricityPrice, local_market_enabled: bool) \
        -> List[Trade]:
    if local_market_enabled:
        # For example: Pbuy_market is how much the LEC bought from the external grid operator
        agent_trades = get_agent_transfers_with_lec(optimized_model, start_datetime,
                                                    sold_internal_name='Psell_grid', bought_internal_name='Pbuy_grid',
                                                    resource=Resource.ELECTRICITY, agent_guids=agent_guids, loss=0.0)
        external_trades = get_external_transfers(optimized_model, start_datetime,
                                                 sold_to_external_name='Psell_market',
                                                 bought_from_external_name='Pbuy_market',
                                                 retail_price_name='price_buy', wholesale_price_name='price_sell',
                                                 resource=Resource.ELECTRICITY, grid_agent_guid=grid_agent_guid,
                                                 loss=0.0, resource_price_data=resource_price_data,
                                                 market=Market.LOCAL)
    else:
        agent_trades = get_agent_transfers_no_lec(optimized_model, start_datetime,
                                                  sold_internal_name='Psell_market', bought_internal_name='Pbuy_market',
                                                  resource=Resource.ELECTRICITY, agent_guid=agent_guids[0], loss=0.0)
        external_trades = get_external_transfers(optimized_model, start_datetime,
                                                 sold_to_external_name='Psell_market',
                                                 bought_from_external_name='Pbuy_market',
                                                 retail_price_name='price_buy', wholesale_price_name='price_sell',
                                                 resource=Resource.ELECTRICITY, grid_agent_guid=grid_agent_guid,
                                                 loss=0.0, resource_price_data=resource_price_data,
                                                 market=Market.EXTERNAL)
    return agent_trades + external_trades


def get_heat_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime, grid_agent_guid: str,
                       agent_guids: List[str], resource_price_data: HeatingPrice, local_market_enabled: bool) \
        -> List[Trade]:
    resource = Resource.LOW_TEMP_HEAT if should_use_summer_mode(start_datetime) else Resource.HIGH_TEMP_HEAT
    if local_market_enabled:
        agent_trades = get_agent_transfers_with_lec(optimized_model, start_datetime,
                                                    sold_internal_name='Hsell_grid', bought_internal_name='Hbuy_grid',
                                                    resource=resource, agent_guids=agent_guids,
                                                    loss=optimized_model.Heat_trans_loss)
        external_trades = get_external_transfers(optimized_model, start_datetime,
                                                 sold_to_external_name='NA', bought_from_external_name='Hbuy_market',
                                                 retail_price_name='Hprice_energy', wholesale_price_name='NA',
                                                 resource=Resource.HIGH_TEMP_HEAT, grid_agent_guid=grid_agent_guid,
                                                 loss=optimized_model.Heat_trans_loss,
                                                 resource_price_data=resource_price_data, market=Market.LOCAL)
    else:
        agent_trades = get_agent_transfers_no_lec(optimized_model, start_datetime,
                                                  sold_internal_name='NA', bought_internal_name='Hbuy_market',
                                                  resource=resource, agent_guid=agent_guids[0],
                                                  loss=optimized_model.Heat_trans_loss)
        external_trades = get_external_transfers(optimized_model, start_datetime,
                                                 sold_to_external_name='NA', bought_from_external_name='Hbuy_market',
                                                 retail_price_name='Hprice_energy', wholesale_price_name='NA',
                                                 resource=Resource.HIGH_TEMP_HEAT, grid_agent_guid=grid_agent_guid,
                                                 loss=optimized_model.Heat_trans_loss,
                                                 resource_price_data=resource_price_data, market=Market.EXTERNAL)
    return agent_trades + external_trades


def get_cool_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime, agent_guids: List[str]) \
        -> List[Trade]:
    return get_agent_transfers_with_lec(optimized_model, start_datetime,
                                        sold_internal_name='Csell_grid', bought_internal_name='Cbuy_grid',
                                        resource=Resource.COOLING, agent_guids=agent_guids,
                                        loss=optimized_model.cold_trans_loss)


def get_external_transfers(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                           sold_to_external_name: str, bought_from_external_name: str,
                           retail_price_name: str, wholesale_price_name: str,
                           resource: Resource, grid_agent_guid: str, loss: float,
                           resource_price_data: IPrice, market: Market) -> List[Trade]:
    transfers: List[Trade] = []
    for hour in optimized_model.T:
        add_external_trade(transfers, bought_from_external_name, hour, optimized_model, sold_to_external_name,
                           retail_price_name, wholesale_price_name, start_datetime, grid_agent_guid, resource, loss,
                           resource_price_data, market)
    return transfers


def get_agent_transfers_with_lec(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                                 sold_internal_name: str, bought_internal_name: str,
                                 resource: Resource, agent_guids: List[str], loss: float) -> List[Trade]:
    transfers: List[Trade] = []
    for hour in optimized_model.T:
        for i_agent in optimized_model.I:
            add_agent_trade(transfers, bought_internal_name, sold_internal_name, hour, i_agent, optimized_model,
                            start_datetime, resource, agent_guids, loss, Market.LOCAL)
    return transfers


def get_agent_transfers_no_lec(optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                               sold_internal_name: str, bought_internal_name: str,
                               resource: Resource, agent_guid: str, loss: float) -> List[Trade]:
    transfers: List[Trade] = []
    for hour in optimized_model.T:
        add_agent_trade(transfers, bought_internal_name, sold_internal_name, hour, None, optimized_model,
                        start_datetime, resource, [agent_guid], loss, Market.EXTERNAL)
    return transfers


def add_agent_trade(trade_list: List[Trade], bought_internal_name: str, sold_internal_name: str, hour: int,
                    i_agent: Optional[int], optimized_model: pyo.ConcreteModel, start_datetime: datetime.datetime,
                    resource: Resource, agent_guids: List[str], loss: float, market: Market):
    bought_internal: IndexedVar = getattr(optimized_model, bought_internal_name)
    sold_internal: Optional[IndexedVar] = getattr(optimized_model, sold_internal_name) \
        if hasattr(optimized_model, sold_internal_name) else None
    if i_agent is not None:
        net = bought_internal[i_agent, hour] - sold_internal[i_agent, hour] \
            if sold_internal is not None else bought_internal[i_agent, hour]
        agent_name = agent_guids[i_agent]
    else:
        net = bought_internal[hour] - sold_internal[hour] \
            if sold_internal is not None else bought_internal[hour]
        agent_name = agent_guids[0]
    quantity = pyo.value(net)
    if quantity > VERY_SMALL_NUMBER or quantity < -VERY_SMALL_NUMBER:
        quantity_pre_loss = quantity / (1 - loss)
        trade_list.append(Trade(period=start_datetime + datetime.timedelta(hours=hour),
                                action=Action.BUY if quantity > 0 else Action.SELL, resource=resource,
                                quantity=abs(quantity_pre_loss if quantity > 0 else quantity), price=np.nan,
                                source=agent_name, by_external=False, market=market, loss=loss))


def add_external_trade(trade_list: List[Trade], bought_from_external_name: str, hour: int,
                       optimized_model: pyo.ConcreteModel, sold_to_external_name: str, retail_price_name: str,
                       wholesale_price_name: str, start_datetime: datetime.datetime, grid_agent_guid: str,
                       resource: Resource, loss: float, resource_price_data: IPrice, market: Market):
    external_quantity = pyo.value(get_variable_value_or_else(optimized_model, sold_to_external_name, hour)
                                  - get_variable_value_or_else(optimized_model, bought_from_external_name, hour))
    period = start_datetime + datetime.timedelta(hours=hour)
    if external_quantity > VERY_SMALL_NUMBER:
        wholesale_prices = getattr(optimized_model, wholesale_price_name)
        price = get_value_from_param(wholesale_prices, hour)
        trade_list.append(Trade(period=period,
                                action=Action.BUY, resource=resource, quantity=external_quantity / (1 - loss),
                                price=price, source=grid_agent_guid, by_external=True, market=market,
                                loss=loss))
    elif external_quantity < -VERY_SMALL_NUMBER:
        retail_prices = getattr(optimized_model, retail_price_name)
        price = get_value_from_param(retail_prices, hour)
        trade_list.append(Trade(period=period,
                                action=Action.SELL, resource=resource, quantity=-external_quantity,
                                price=price, source=grid_agent_guid, by_external=True, market=market,
                                loss=loss,
                                tax_paid=resource_price_data.tax, grid_fee_paid=resource_price_data.grid_fee))
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
