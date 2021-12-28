import datetime
import json
import logging

from typing import List

from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.market_solver import MarketSolver
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc import balance_manager, results_calculator
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import ElectricityGridAgent
from tradingplatformpoc.agent.grocery_store_agent import GroceryStoreAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.agent.storage_agent import BatteryStorageAgent
from tradingplatformpoc.trade import write_rows
from tradingplatformpoc.bid import Bid

logger = logging.getLogger(__name__)


def run_trading_simulations():
    """The core loop of the simulation, running through the desired time period and performing trades."""

    logger.info("Starting trading simulations")

    with open("../data/jonstaka.json", "r") as jsonfile:
        config_data = json.load(jsonfile)

    # Initialize data store
    data_store_entity = DataStore(config_data=config_data["AreaInfo"])

    # Output files
    clearing_prices_file = open('../clearing_prices.csv', 'w')
    clearing_prices_file.write('period,price\n')
    trades_csv_file = open('../trades.csv', 'w')
    trades_csv_file.write('period,agent,by_external,action,resource,market,quantity,price\n')
    extra_costs_file = open('../extra_costs.csv', 'w')
    extra_costs_file.write('period,agent,cost\n')
    # Output lists
    clearing_prices_dict = {}
    all_trades_list = []
    all_extra_costs_dict = {}

    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent]
    try:
        agents, grid_agent = initialize_agents(data_store_entity, config_data)
    except RuntimeError as e:
        clearing_prices_file.write(e.args)
        exit(1)

    # Get a market solver
    market_solver = MarketSolver()

    # Main loop
    trading_periods = data_store_entity.get_trading_periods()
    for period in trading_periods:
        # Get all bids
        bids = [agent.make_bids(period) for agent in agents]

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
        trades_excl_external = [agent.make_trade_given_clearing_price(period, clearing_price) for agent in agents]
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


def initialize_agents(data_store_entity, config_data):
    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent] = []

    for agent in config_data["Agents"]:
        agent_type = agent["Type"]
        if agent_type == "BuildingAgent":
            building_digital_twin = StaticDigitalTwin(electricity_usage=data_store_entity.tornet_household_elec_cons,
                                                      heating_usage=data_store_entity.tornet_heat_cons)
            agents.append(BuildingAgent(data_store_entity, building_digital_twin))
        elif agent_type == "BatteryStorageAgent":
            storage_digital_twin = StorageDigitalTwin(max_capacity_kwh=agent["Capacity"],
                                                      max_charge_rate_fraction=agent["ChargeRate"],
                                                      max_discharge_rate_fraction=agent["ChargeRate"])
            agents.append(BatteryStorageAgent(data_store_entity, storage_digital_twin))
        elif agent_type == "PVAgent":
            pv_digital_twin = StaticDigitalTwin(electricity_production=data_store_entity.tornet_pv_prod)
            agents.append(PVAgent(data_store_entity, pv_digital_twin))
        elif agent_type == "GroceryStoreAgent":
            grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=data_store_entity.coop_elec_cons,
                                                           heating_usage=data_store_entity.coop_heat_cons,
                                                           electricity_production=data_store_entity.coop_pv_prod)
            agents.append(GroceryStoreAgent(data_store_entity, grocery_store_digital_twin))
        elif agent_type == "ElectricityGridAgent":
            grid_agent = ElectricityGridAgent(data_store_entity, max_transfer_per_hour=agent["TransferRate"])
            agents.append(grid_agent)

    # TODO: As of right now, grid agents are treated as configurable, but the code is hard coded with the
    # TODO: assumption that they'll always exist. Should probably be refactored

    # Verify that we have a Grid Agent
    if not any(isinstance(agent, ElectricityGridAgent) for agent in agents):
        raise RuntimeError("No grid agent initialized")

    return agents, grid_agent


def get_corresponding_digital_twin(agent_name, digital_twins):
    if agent_name not in digital_twins:
        raise RuntimeError("No digital twin found for agent {}".format(agent_name))
    return digital_twins[agent_name]


def write_extra_costs_rows(period: datetime.datetime, extra_costs: dict):
    full_string = ""
    for k, v in extra_costs.items():
        if v != 0:
            full_string = full_string + str(period) + "," + k + "," + str(v) + "\n"
    return full_string
