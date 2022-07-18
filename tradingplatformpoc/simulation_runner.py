import datetime
import logging
import pickle
from typing import Any, Collection, Dict, List, Tuple, Union

import pandas as pd

from pkg_resources import resource_filename

import streamlit as st

from tradingplatformpoc import balance_manager, data_store, generate_mock_data, market_solver, results_calculator
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.balance_manager import correct_for_exact_heating_price
from tradingplatformpoc.bid import Action, Bid, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.extra_cost import ExtraCost
from tradingplatformpoc.mock_data_generation_functions import MockDataKey, get_all_building_agents, get_elec_cons_key, \
    get_heat_cons_key, get_pv_prod_key
from tradingplatformpoc.simulation_results import SimulationResults
from tradingplatformpoc.trade import Trade, TradeMetadataKey
from tradingplatformpoc.trading_platform_utils import add_to_nested_dict, calculate_solar_prod, flatten_collection, \
    get_if_exists_else, get_intersection

FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED = 0.06

logger = logging.getLogger(__name__)


def run_trading_simulations(config_data: Dict[str, Any], mock_datas_pickle_path: str, progress_bar:
                            Union[st.progress, None] = None, progress_text: Union[st.info, None] = None) -> \
        SimulationResults:
    """
    The core loop of the simulation, running through the desired time period and performing trades.
    @param config_data              A dict specifying some configuration data
    @param mock_datas_pickle_path   A string specifying the location to look for saved mock data
    @param progress_bar             A streamlit progress bar, used only when running simulations through the UI
    @param progress_text            A streamlit info field, used only when running simulations through the UI
    """

    frac_complete = 0.0  # Annoyingly, we must keep track of this separately, can't "get" progress from the progress bar
    logger.info("Starting trading simulations")

    # Initialize data store
    data_store_entity = DataStore.from_csv_files(config_area_info=config_data["AreaInfo"])

    # Specify path for CSV files from which to take some mock data (currently only for grocery store)
    energy_data_csv_path = resource_filename("tradingplatformpoc.data", "full_mock_energy_data.csv")

    # Load generated mock data
    buildings_mock_data: pd.DataFrame = get_generated_mock_data(config_data, mock_datas_pickle_path)

    # Output lists
    clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]] = {}
    all_trades_dict: Dict[datetime.datetime, Collection[Trade]] = {}
    all_bids_dict: Dict[datetime.datetime, Collection[BidWithAcceptanceStatus]] = {}
    storage_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}
    heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}
    all_extra_costs: List[ExtraCost] = []
    # Store the exact external prices, need them for some calculations
    exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float] = {}
    exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float] = {}

    # Register all agents
    # Keep a list of all agents to iterate over later
    agents, grid_agents = initialize_agents(data_store_entity, config_data, buildings_mock_data, energy_data_csv_path)

    # Main loop
    trading_periods = get_intersection(buildings_mock_data.index.tolist(),
                                       data_store_entity.get_nordpool_data_datetimes())
    for period in trading_periods:
        if period.day == period.hour == 1:
            info_string = "Simulations entering {:%B}".format(period)
            logger.info(info_string)
            if progress_bar is not None:
                frac_complete = increase_progress_bar(frac_complete, progress_bar,
                                                      FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED)
            if progress_text is not None:
                progress_text.info(info_string + "...")

        # Get all bids
        bids = [agent.make_bids(period, clearing_prices_historical) for agent in agents]

        # Flatten bids list
        bids_flat: List[Bid] = flatten_collection(bids)

        # Resolve bids
        clearing_prices, bids_with_acceptance_status = market_solver.resolve_bids(period, bids_flat)
        clearing_prices_historical[period] = clearing_prices

        all_bids_dict[period] = bids_with_acceptance_status

        # Send clearing price back to agents, allow them to "make trades", i.e. decide if they want to buy/sell
        # energy, from/to either the local market or directly from/to the external grid.
        # To be clear: These "trades" are for _actual_ amounts, not predicted. All agents except the external grid agent
        # makes these, then finally the external grid agent "fills in" the energy imbalances through "trades" of its own
        trades_excl_external = []
        for agent in agents:
            accepted_bids_for_agent = [bid for bid in bids_with_acceptance_status
                                       if bid.source == agent.guid and bid.accepted_quantity > 0]
            trades, metadata = agent.make_trades_given_clearing_price(period, clearing_prices, accepted_bids_for_agent)
            trades_excl_external.extend(trades)
            go_through_trades_metadata(metadata, period, agent.guid, heat_pump_levels_dict, storage_levels_dict)

        trades_excl_external = [i for i in trades_excl_external if i]  # filter out None
        external_trades = flatten_collection([ga.calculate_external_trades(trades_excl_external, clearing_prices)
                                              for ga in grid_agents])
        all_trades_for_period = trades_excl_external + external_trades
        all_trades_dict[period] = all_trades_for_period

        external_heating_sell_quantity = get_quantity_heating_sold_by_external_grid(external_trades)
        data_store_entity.add_external_heating_sell(period, external_heating_sell_quantity)

        wholesale_price_elec = data_store_entity.get_exact_wholesale_price(period, Resource.ELECTRICITY)
        retail_price_elec = data_store_entity.get_exact_retail_price(period, Resource.ELECTRICITY)
        wholesale_prices = {Resource.ELECTRICITY: wholesale_price_elec,
                            Resource.HEATING: data_store_entity.get_estimated_wholesale_price(period, Resource.HEATING)}
        extra_costs = balance_manager.calculate_penalty_costs_for_period(bids_with_acceptance_status,
                                                                         all_trades_for_period,
                                                                         period,
                                                                         clearing_prices,
                                                                         wholesale_prices)
        exact_wholesale_electricity_prices_by_period[period] = wholesale_price_elec
        exact_retail_electricity_prices_by_period[period] = retail_price_elec
        all_extra_costs.extend(extra_costs)

    if progress_bar is not None:
        frac_complete = increase_progress_bar(frac_complete, progress_bar,
                                              FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED + 0.01)
    if progress_text is not None:
        progress_text.info("Simulated a full year, starting some calculations on district heating price...")

    # Simulations finished. Now, we need to go through and calculate the exact district heating price for each month
    estimated_retail_heating_prices_by_year_and_month, \
        estimated_wholesale_heating_prices_by_year_and_month, \
        exact_retail_heating_prices_by_year_and_month, \
        exact_wholesale_heating_prices_by_year_and_month = get_external_heating_prices(data_store_entity,
                                                                                       trading_periods)

    heat_cost_discr_corrections = correct_for_exact_heating_price(trading_periods, all_trades_dict,
                                                                  exact_retail_heating_prices_by_year_and_month,
                                                                  exact_wholesale_heating_prices_by_year_and_month,
                                                                  estimated_retail_heating_prices_by_year_and_month,
                                                                  estimated_wholesale_heating_prices_by_year_and_month)
    all_extra_costs.extend(heat_cost_discr_corrections)

    results_calculator.print_basic_results(agents, all_trades_dict, all_extra_costs,
                                           exact_retail_electricity_prices_by_period,
                                           exact_wholesale_electricity_prices_by_period,
                                           exact_retail_heating_prices_by_year_and_month,
                                           exact_wholesale_heating_prices_by_year_and_month)

    if progress_bar is not None:
        frac_complete = increase_progress_bar(frac_complete, progress_bar, 0.01)
    if progress_text is not None:
        progress_text.info("Formatting results...")

    extra_costs_df = pd.DataFrame([x.to_series() for x in all_extra_costs]).sort_values(['period', 'agent'])
    all_trades_df, frac_complete = construct_df_from_datetime_dict(all_trades_dict, progress_bar, frac_complete)
    all_bids_df, frac_complete = construct_df_from_datetime_dict(all_bids_dict, progress_bar, frac_complete)
    return SimulationResults(clearing_prices_historical=clearing_prices_historical,
                             all_trades=all_trades_df,
                             all_extra_costs=extra_costs_df,
                             all_bids=all_bids_df,
                             storage_levels_dict=storage_levels_dict,
                             heat_pump_levels_dict=heat_pump_levels_dict,
                             config_data=config_data,
                             agents=agents,
                             data_store=data_store_entity)


def increase_progress_bar(frac_complete: float, progress_bar: st.progress, increase_by: float):
    """
    Increases the progress bar, and returns its current value.
    """
    # Capping at 0.0 and 1.0 to avoid StreamlitAPIException
    new_frac_complete = min(1.0, max(0.0, frac_complete + increase_by))
    progress_bar.progress(new_frac_complete)
    return new_frac_complete


def go_through_trades_metadata(metadata: Dict[TradeMetadataKey, Any], period: datetime.datetime, agent_guid: str,
                               heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]],
                               storage_levels_dict: Dict[str, Dict[datetime.datetime, float]]):
    """
    The agent may want to send some metadata along with its trade, to the simulation runner. Any such metadata is dealt
    with here.
    """
    for metadata_key in metadata:
        if metadata_key == TradeMetadataKey.STORAGE_LEVEL:
            capacity_for_agent = metadata[metadata_key]
            add_to_nested_dict(storage_levels_dict, agent_guid, period, capacity_for_agent)
        elif metadata_key == TradeMetadataKey.HEAT_PUMP_WORKLOAD:
            current_heat_pump_level = metadata[metadata_key]
            add_to_nested_dict(heat_pump_levels_dict, agent_guid, period, current_heat_pump_level)
        else:
            logger.info('Encountered unexpected metadata! Key: {}, Value: {}'.
                        format(metadata_key, metadata[metadata_key]))


def get_external_heating_prices(data_store_entity: DataStore, trading_periods: Collection[datetime.datetime]) -> \
        Tuple[Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float]]:
    exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    estimated_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    estimated_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    for (year, month) in set([(dt.year, dt.month) for dt in trading_periods]):
        first_day_of_month = datetime.datetime(year, month, 1)  # Which day it is doesn't matter
        exact_retail_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_exact_retail_price(first_day_of_month, Resource.HEATING)
        exact_wholesale_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_exact_wholesale_price(first_day_of_month, Resource.HEATING)
        estimated_retail_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_estimated_retail_price(first_day_of_month, Resource.HEATING)
        estimated_wholesale_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_estimated_wholesale_price(first_day_of_month, Resource.HEATING)
    return estimated_retail_heating_prices_by_year_and_month, \
        estimated_wholesale_heating_prices_by_year_and_month, \
        exact_retail_heating_prices_by_year_and_month, \
        exact_wholesale_heating_prices_by_year_and_month


def get_generated_mock_data(config_data: dict, mock_datas_pickle_path: str) -> pd.DataFrame:
    """
    Loads the dict stored in MOCK_DATAS_PICKLE, checks if it contains a key which is identical to the set of building
    agents specified in config_data. If it isn't, throws an error. If it is, it returns the value for that key in the
    dictionary.
    @param config_data: A dictionary specifying agents etc
    @param mock_datas_pickle_path: Path to pickle file where dict with mock data is saved
    @return: A pd.DataFrame containing mock data for building agents
    """
    with open(mock_datas_pickle_path, 'rb') as f:
        all_data_sets = pickle.load(f)
    building_agents, total_gross_floor_area = get_all_building_agents(config_data["Agents"])
    mock_data_key = MockDataKey(frozenset(building_agents), config_data["AreaInfo"]["DefaultPVEfficiency"])
    if mock_data_key not in all_data_sets:
        logger.info("No mock data found for this configuration. Running mock data generation.")
        all_data_sets = generate_mock_data.run(config_data)
        logger.info("Finished mock data generation.")
    return all_data_sets[mock_data_key]


def initialize_agents(data_store_entity: DataStore, config_data: dict, buildings_mock_data: pd.DataFrame,
                      energy_data_csv_path: str) -> Tuple[List[IAgent], List[GridAgent]]:
    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent] = []
    grid_agents: List[GridAgent] = []

    # Read energy CSV file
    tornet_household_elec_cons, coop_elec_cons, tornet_heat_cons, coop_heat_cons = \
        data_store.read_energy_data(energy_data_csv_path)

    for agent in config_data["Agents"]:
        agent_type = agent["Type"]
        agent_name = agent['Name']
        if agent_type == "BuildingAgent":
            elec_cons_series = buildings_mock_data[get_elec_cons_key(agent_name)]
            heat_cons_series = buildings_mock_data[get_heat_cons_key(agent_name)]
            pv_prod_series = buildings_mock_data[get_pv_prod_key(agent_name)]

            building_digital_twin = StaticDigitalTwin(electricity_usage=elec_cons_series,
                                                      electricity_production=pv_prod_series,
                                                      heating_usage=heat_cons_series)

            nbr_heat_pumps = agent["NumberHeatPumps"] if "NumberHeatPumps" in agent.keys() else 0
            cop = agent["COP"] if "COP" in agent.keys() else None

            agents.append(BuildingAgent(data_store=data_store_entity, digital_twin=building_digital_twin,
                                        guid=agent_name, nbr_heat_pumps=nbr_heat_pumps, coeff_of_perf=cop))

        elif agent_type == "StorageAgent":
            discharge_rate = agent["DischargeRate"] if "DischargeRate" in agent else agent["ChargeRate"]
            storage_digital_twin = StorageDigitalTwin(max_capacity_kwh=agent["Capacity"],
                                                      max_charge_rate_fraction=agent["ChargeRate"],
                                                      max_discharge_rate_fraction=discharge_rate,
                                                      discharging_efficiency=agent["RoundTripEfficiency"])
            agents.append(StorageAgent(data_store_entity, storage_digital_twin,
                                       resource=Resource[agent["Resource"]],
                                       n_hours_to_look_back=agent["NHoursBack"],
                                       buy_price_percentile=agent["BuyPricePercentile"],
                                       sell_price_percentile=agent["SellPricePercentile"],
                                       guid=agent_name))
        elif agent_type == "PVAgent":
            pv_efficiency = get_if_exists_else(agent, 'PVEfficiency', data_store_entity.default_pv_efficiency)
            pv_prod_series = calculate_solar_prod(data_store_entity.irradiation_data, agent['PVArea'], pv_efficiency)
            pv_digital_twin = StaticDigitalTwin(electricity_production=pv_prod_series)
            agents.append(PVAgent(data_store_entity, pv_digital_twin, guid=agent_name))
        elif agent_type == "GroceryStoreAgent":
            pv_efficiency = get_if_exists_else(agent, 'PVEfficiency', data_store_entity.default_pv_efficiency)
            pv_area = agent['PVArea'] if 'PVArea' in agent else 0
            pv_prod_series = calculate_solar_prod(data_store_entity.irradiation_data, pv_area, pv_efficiency)
            grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=coop_elec_cons,
                                                           heating_usage=coop_heat_cons,
                                                           electricity_production=pv_prod_series)
            agents.append(BuildingAgent(data_store=data_store_entity, digital_twin=grocery_store_digital_twin,
                                        guid=agent_name))
        elif agent_type == "GridAgent":
            grid_agent = GridAgent(data_store_entity, Resource[agent["Resource"]],
                                   max_transfer_per_hour=agent["TransferRate"], guid=agent_name)
            agents.append(grid_agent)
            grid_agents.append(grid_agent)

    # Verify that we have a Grid Agent
    if not any(isinstance(agent, GridAgent) for agent in agents):
        raise RuntimeError("No grid agent initialized")

    return agents, grid_agents


def get_quantity_heating_sold_by_external_grid(external_trades: List[Trade]) -> float:
    return sum([x.quantity for x in external_trades if
                (x.resource == Resource.HEATING) & (x.action == Action.SELL)])


def construct_df_from_datetime_dict(some_dict: Union[Dict[datetime.datetime, Collection[BidWithAcceptanceStatus]],
                                                     Dict[datetime.datetime, Collection[Trade]]],
                                    progress_bar: Union[st.progress, None] = None, frac_complete: float = 0.0) \
        -> Tuple[pd.DataFrame, float]:
    """
    Streamlit likes to deal with pd.DataFrames, so we'll save data in that format.
    Takes a little while to run - about 20 seconds for an input with 8760 keys and 30-35 entries per key.

    progress_bar and frac_complete are only used when called from the UI, to show progress to the user.
    """
    logger.info('Constructing dataframe from datetime dict')
    series_list = []
    for (period, some_collection) in some_dict.items():
        series_list.extend([x.to_series_with_period(period) for x in some_collection])
    data_frame = pd.DataFrame(series_list)

    if progress_bar is not None:
        frac_complete = increase_progress_bar(frac_complete, progress_bar, 0.1)
    return data_frame, frac_complete
