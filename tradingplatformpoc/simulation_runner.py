import datetime
import json
import logging
import pickle

from typing import List

import pandas as pd

from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.market_solver import MarketSolver
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc import balance_manager, results_calculator, data_store
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import ElectricityGridAgent
from tradingplatformpoc.agent.grocery_store_agent import GroceryStoreAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.mock_data_generation_functions import get_all_building_agents, get_pv_prod_key, \
    get_elec_cons_key
from tradingplatformpoc.trade import write_rows
from tradingplatformpoc.bid import Bid
from pkg_resources import resource_filename

logger = logging.getLogger(__name__)


def run_trading_simulations(mock_datas_pickle_path: str):
    """The core loop of the simulation, running through the desired time period and performing trades."""

    logger.info("Starting trading simulations")

    with open(resource_filename("tradingplatformpoc.data", "jonstaka.json"), "r") as jsonfile:
        config_data = json.load(jsonfile)

    # Initialize data store
    data_store_entity = DataStore(config_area_info=config_data["AreaInfo"])

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
    clearing_prices_dict = {}
    all_trades_list = []
    all_extra_costs_dict = {}

    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent]
    try:
        agents, grid_agent = initialize_agents(data_store_entity, config_data, buildings_mock_data)
    except RuntimeError as e:
        clearing_prices_file.write(e.args)
        exit(1)

    # Get a market solver
    market_solver = MarketSolver()

    # Main loop
    trading_periods = data_store_entity.get_trading_periods()
    for period in trading_periods:
        # Get all bids
        bids = [agent.make_bids(period, clearing_prices_dict) for agent in agents]

        # Flatten bids list
        bids_flat: List[Bid] = [bid for sublist in bids for bid in sublist]

        # Resolve bids
        try:
            clearing_price = market_solver.resolve_bids(bids_flat)
        except RuntimeError as e:
            clearing_price = e.args
        clearing_prices_dict[period] = clearing_price

        clearing_prices_file.write('{},{}\n'.format(period, clearing_price))

        # Send clearing price back to agents, allow them to "make trades", i.e. decide if they want to buy/sell
        # energy, from/to either the local market or directly from/to the external grid.
        # To be clear: These "trades" are for _actual_ amounts, not predicted. All agents except the external grid agent
        # makes these, then finally the external grid agent "fills in" the energy imbalances through "trades" of its own
        trades_excl_external = [agent.make_trade_given_clearing_price(period, clearing_price, clearing_prices_dict)
                                for agent in agents]
        trades_excl_external = [i for i in trades_excl_external if i]  # filter out None
        external_trades = grid_agent.calculate_external_trades(trades_excl_external, clearing_price)
        all_trades_for_period = trades_excl_external + external_trades
        trades_csv_file.write(write_rows(all_trades_for_period))
        all_trades_list.extend(all_trades_for_period)

        wholesale_price = data_store_entity.get_wholesale_price(period)
        extra_costs = balance_manager.calculate_costs(bids_flat, all_trades_for_period, clearing_price, wholesale_price)
        extra_costs_file.write(write_extra_costs_rows(period, extra_costs))
        all_extra_costs_dict[period] = extra_costs

    # Exit gracefully
    clearing_prices_file.close()
    trades_csv_file.close()
    extra_costs_file.close()

    results_calculator.print_basic_results(agents, all_trades_list, all_extra_costs_dict, data_store_entity)

    return clearing_prices_dict, all_trades_list, all_extra_costs_dict


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
    building_agents, total_gross_floor_area = get_all_building_agents(config_data)
    building_agents_frozen_set = frozenset(building_agents)  # Need to freeze, else can't use it as key in dict
    if building_agents_frozen_set not in all_data_sets:
        raise RuntimeError('No mock data found for this configuration!')
    else:
        return all_data_sets[building_agents_frozen_set]


def initialize_agents(data_store_entity: data_store, config_data: dict, buildings_mock_data: pd.DataFrame):
    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent] = []

    for agent in config_data["Agents"]:
        agent_type = agent["Type"]
        if agent_type == "BuildingAgent":
            agent_name = agent['Name']
            household_elec_cons_series = buildings_mock_data[get_elec_cons_key(agent_name)]
            pv_prod_series = buildings_mock_data[get_pv_prod_key(agent_name)]
            building_digital_twin = StaticDigitalTwin(electricity_usage=household_elec_cons_series,
                                                      electricity_production=pv_prod_series)
            agents.append(BuildingAgent(data_store_entity, building_digital_twin, guid=agent_name))
        elif agent_type == "StorageAgent":
            storage_digital_twin = StorageDigitalTwin(max_capacity_kwh=agent["Capacity"],
                                                      max_charge_rate_fraction=agent["ChargeRate"],
                                                      max_discharge_rate_fraction=agent["ChargeRate"])
            agents.append(StorageAgent(data_store_entity, storage_digital_twin,
                                       n_hours_to_look_back=agent["NHoursBack"],
                                       buy_price_percentile=agent["BuyPricePercentile"],
                                       sell_price_percentile=agent["SellPricePercentile"],
                                       guid=agent["Name"]))
        elif agent_type == "PVAgent":
            pv_digital_twin = StaticDigitalTwin(electricity_production=data_store_entity.tornet_park_pv_prod)
            agents.append(PVAgent(data_store_entity, pv_digital_twin, guid=agent["Name"]))
        elif agent_type == "GroceryStoreAgent":
            grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=data_store_entity.coop_elec_cons,
                                                           heating_usage=data_store_entity.coop_heat_cons,
                                                           electricity_production=data_store_entity.coop_pv_prod)
            agents.append(GroceryStoreAgent(data_store_entity, grocery_store_digital_twin, guid=agent["Name"]))
        elif agent_type == "ElectricityGridAgent":
            grid_agent = ElectricityGridAgent(data_store_entity, max_transfer_per_hour=agent["TransferRate"],
                                              guid=agent["Name"])
            agents.append(grid_agent)

    # TODO: As of right now, grid agents are treated as configurable, but the code is hard coded with the
    # TODO: assumption that they'll always exist. Should probably be refactored

    # Verify that we have a Grid Agent
    if not any(isinstance(agent, ElectricityGridAgent) for agent in agents):
        raise RuntimeError("No grid agent initialized")

    return agents, grid_agent


def write_extra_costs_rows(period: datetime.datetime, extra_costs: dict):
    full_string = ""
    for k, v in extra_costs.items():
        if v != 0:
            full_string = full_string + str(period) + "," + k + "," + str(v) + "\n"
    return full_string
