import datetime
import json
import logging
import pickle
from typing import Dict, List

import pandas as pd

from pkg_resources import resource_filename

from tradingplatformpoc import balance_manager, data_store, market_solver, results_calculator
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.bid import Bid, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.mock_data_generation_functions import get_all_residential_building_agents, get_elec_cons_key, \
    get_heat_cons_key, get_pv_prod_key
from tradingplatformpoc.trade import write_rows
from tradingplatformpoc.trading_platform_utils import flatten_collection, get_intersection

logger = logging.getLogger(__name__)


def run_trading_simulations(mock_datas_pickle_path: str):
    """The core loop of the simulation, running through the desired time period and performing trades."""

    logger.info("Starting trading simulations")

    with open(resource_filename("tradingplatformpoc.data", "jonstaka.json"), "r") as jsonfile:
        config_data = json.load(jsonfile)

    # Initialize data store
    data_store_entity = DataStore.from_csv_files(config_area_info=config_data["AreaInfo"])

    # Specify path for CSV files from which to take some mock data (currently only for grocery store)
    energy_data_csv_path = resource_filename("tradingplatformpoc.data", "full_mock_energy_data.csv")
    school_data_csv_path = resource_filename("tradingplatformpoc.data", "school_electricity_consumption.csv")

    # Load generated mock data
    buildings_mock_data = get_generated_mock_data(config_data, mock_datas_pickle_path)

    # Output files
    clearing_prices_file = open('./clearing_prices.csv', 'w')
    clearing_prices_file.write('period,price\n')
    trades_csv_file = open('./trades.csv', 'w')
    trades_csv_file.write('period,agent,by_external,action,resource,market,quantity,price\n')
    extra_costs_file = open('./extra_costs.csv', 'w')
    extra_costs_file.write('period,agent,cost\n')
    # Output lists
    clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]] = {}
    all_trades_list = []
    all_bids_list = []
    all_extra_costs_dict = {}

    # Register all agents
    # Keep a list of all agents to iterate over later
    agents, grid_agents = initialize_agents(data_store_entity, config_data, buildings_mock_data,
                                            energy_data_csv_path, school_data_csv_path)

    # Main loop
    trading_periods = get_intersection(buildings_mock_data.index.tolist(),
                                       data_store_entity.get_nordpool_data_datetimes())
    for period in trading_periods:
        # Get all bids
        bids = [agent.make_bids(period, clearing_prices_historical) for agent in agents]

        # Flatten bids list
        bids_flat: List[Bid] = flatten_collection(bids)

        # Resolve bids
        clearing_prices, bids_with_acceptance_status = market_solver.resolve_bids(period, bids_flat)
        clearing_prices_historical[period] = clearing_prices

        clearing_prices_file.write('{},{}\n'.format(period, clearing_prices))
        all_bids_list.extend(bids_with_acceptance_status)

        # Send clearing price back to agents, allow them to "make trades", i.e. decide if they want to buy/sell
        # energy, from/to either the local market or directly from/to the external grid.
        # To be clear: These "trades" are for _actual_ amounts, not predicted. All agents except the external grid agent
        # makes these, then finally the external grid agent "fills in" the energy imbalances through "trades" of its own
        trades_excl_external = []
        for agent in agents:
            accepted_bids_for_agent = [bid for bid in bids_with_acceptance_status
                                       if bid.source == agent.guid and bid.was_accepted]
            trades_excl_external.extend(
                agent.make_trades_given_clearing_price(period, clearing_prices, accepted_bids_for_agent))

        trades_excl_external = [i for i in trades_excl_external if i]  # filter out None
        external_trades = flatten_collection([ga.calculate_external_trades(trades_excl_external, clearing_prices)
                                              for ga in grid_agents])
        all_trades_for_period = trades_excl_external + external_trades
        trades_csv_file.write(write_rows(all_trades_for_period))
        all_trades_list.extend(all_trades_for_period)

        wholesale_price_elec = data_store_entity.get_exact_wholesale_price(period, Resource.ELECTRICITY)
        wholesale_price_heat = data_store_entity.get_exact_wholesale_price(period, Resource.HEATING)
        extra_costs = balance_manager.calculate_costs(bids_with_acceptance_status, all_trades_for_period,
                                                      clearing_prices, wholesale_price_elec, wholesale_price_heat)
        extra_costs_file.write(write_extra_costs_rows(period, extra_costs))
        all_extra_costs_dict[period] = extra_costs

    # Exit gracefully
    clearing_prices_file.close()
    trades_csv_file.close()
    extra_costs_file.close()

    results_calculator.print_basic_results(agents, all_trades_list, all_extra_costs_dict, data_store_entity)

    return clearing_prices_historical, all_trades_list, all_extra_costs_dict


def get_generated_mock_data(config_data: dict, mock_datas_pickle_path: str):
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
    residential_building_agents, total_gross_floor_area = get_all_residential_building_agents(config_data)
    # Need to freeze, else can't use it as key in dict
    residential_building_agents_frozen_set = frozenset(residential_building_agents)
    if residential_building_agents_frozen_set not in all_data_sets:
        raise RuntimeError('No mock data found for this configuration!')
    else:
        return all_data_sets[residential_building_agents_frozen_set]


def initialize_agents(data_store_entity: DataStore, config_data: dict, buildings_mock_data: pd.DataFrame,
                      energy_data_csv_path: str, school_data_csv_path: str):
    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent] = []
    grid_agents: List[GridAgent] = []

    # Read energy CSV file
    tornet_household_elec_cons, coop_elec_cons, tornet_heat_cons, coop_heat_cons = \
        data_store.read_energy_data(energy_data_csv_path)
    # Read school CSV file
    school_elec_cons = data_store.read_school_energy_consumption_csv(school_data_csv_path)

    for agent in config_data["Agents"]:
        agent_type = agent["Type"]
        agent_name = agent['Name']
        if agent_type == "ResidentialBuildingAgent":
            elec_cons_series = buildings_mock_data[get_elec_cons_key(agent_name)]
            heat_cons_series = buildings_mock_data[get_heat_cons_key(agent_name)]
            pv_prod_series = buildings_mock_data[get_pv_prod_key(agent_name)]
            building_digital_twin = StaticDigitalTwin(electricity_usage=elec_cons_series,
                                                      electricity_production=pv_prod_series,
                                                      heating_usage=heat_cons_series)
            agents.append(BuildingAgent(data_store_entity, building_digital_twin, guid=agent_name))
        elif agent_type == "StorageAgent":
            storage_digital_twin = StorageDigitalTwin(max_capacity_kwh=agent["Capacity"],
                                                      max_charge_rate_fraction=agent["ChargeRate"],
                                                      max_discharge_rate_fraction=agent["ChargeRate"],
                                                      discharging_efficiency=agent["RoundTripEfficiency"])
            agents.append(StorageAgent(data_store_entity, storage_digital_twin,
                                       resource=Resource[agent["Resource"]],
                                       n_hours_to_look_back=agent["NHoursBack"],
                                       buy_price_percentile=agent["BuyPricePercentile"],
                                       sell_price_percentile=agent["SellPricePercentile"],
                                       guid=agent_name))
        elif agent_type == "PVAgent":
            pv_digital_twin = StaticDigitalTwin(electricity_production=data_store_entity.tornet_park_pv_prod)
            agents.append(PVAgent(data_store_entity, pv_digital_twin, guid=agent_name))
        elif agent_type == "CommercialBuildingAgent":
            if agent_name == "GroceryStoreAgent":
                grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=coop_elec_cons,
                                                               heating_usage=coop_heat_cons,
                                                               electricity_production=data_store_entity.coop_pv_prod)
                agents.append(BuildingAgent(data_store_entity, grocery_store_digital_twin, guid=agent_name))
            if agent_name == "SchoolBuildingAgent":
                school_digital_twin = StaticDigitalTwin(electricity_usage=school_elec_cons)
                agents.append(BuildingAgent(data_store_entity, school_digital_twin, guid=agent_name))
        elif agent_type == "GridAgent":
            grid_agent = GridAgent(data_store_entity, Resource[agent["Resource"]],
                                   max_transfer_per_hour=agent["TransferRate"], guid=agent_name)
            agents.append(grid_agent)
            grid_agents.append(grid_agent)

    # Verify that we have a Grid Agent
    if not any(isinstance(agent, GridAgent) for agent in agents):
        raise RuntimeError("No grid agent initialized")

    return agents, grid_agents


def write_extra_costs_rows(period: datetime.datetime, extra_costs: dict):
    full_string = ""
    for k, v in extra_costs.items():
        if v != 0:
            full_string = full_string + str(period) + "," + k + "," + str(v) + "\n"
    return full_string
