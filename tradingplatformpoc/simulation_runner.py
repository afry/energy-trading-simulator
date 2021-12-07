import json

from typing import List

from tradingplatformpoc.market_solver import MarketSolver
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc import balance_manager
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import ElectricityGridAgent
from tradingplatformpoc.agent.grocery_store_agent import GroceryStoreAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.agent.storage_agent import BatteryStorageAgent
from tradingplatformpoc.trade import write_rows
from tradingplatformpoc.bid import Bid


def run_trading_simulations():
    """The core loop of the simulation, running through the desired time period and performing trades."""

    with open("../data/jonstaka.json", "r") as jsonfile:
        config_data = json.load(jsonfile)

    # Initialize data store
    data_store_entity = DataStore(config_data=config_data["AreaInfo"])

    # Output files
    log_file = open('../log.txt', 'w')
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
        log_file.write(e.args)
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

        log_entry = 'Time period: {}, price: {}\n'. \
            format(period, clearing_price)
        log_file.write(log_entry)

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
    log_file.close()
    trades_csv_file.close()
    extra_costs_file.close()

    return clearing_prices_dict, all_trades_list, all_extra_costs_dict


def initialize_agents(data_store_entity, config_data):
    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent] = []

    for agent in config_data["Agents"]:
        agent_type = agent["Name"]
        if agent_type == "BuildingAgent":
            agents.append(BuildingAgent(data_store_entity))
        elif agent_type == "BatteryStorageAgent":
            agents.append(BatteryStorageAgent(data_store_entity, max_capacity=agent["Capacity"],
                                              charge_rate=agent["ChargeRate"]))
        elif agent_type == "PVAgent":
            agents.append(PVAgent(data_store_entity))
        elif agent_type == "GroceryStoreAgent":
            agents.append(GroceryStoreAgent(data_store_entity))
        elif agent_type == "ElectricityGridAgent":
            grid_agent = ElectricityGridAgent(data_store_entity, max_transfer_per_hour=agent["TransferRate"])
            agents.append(grid_agent)

    # TODO: As of right now, grid agents are treated as configurable, but the code is hard coded with the
    # TODO: assumption that they'll always exist. Should probably be refactored

    # Verify that we have a Grid Agent
    if not any(isinstance(agent, ElectricityGridAgent) for agent in agents):
        raise RuntimeError("No grid agent initialized")

    return agents, grid_agent


def write_extra_costs_rows(period, extra_costs):
    full_string = ""
    for k, v in extra_costs.items():
        if v != 0:
            full_string = full_string + period + "," + k + "," + str(v) + "\n"
    return full_string
