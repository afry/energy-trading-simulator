import json

from typing import List
from bid import Bid
from market_solver import MarketSolver
from data_store import DataStore
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import ElectricityGridAgent
from tradingplatformpoc.agent.grocery_store_agent import GroceryStoreAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.agent.storage_agent import BatteryStorageAgent
from trade import write_rows


def main():
    """The core loop of the simulation, running through the desired time period and performing trades."""

    with open("../data/jonstaka.json", "r") as jsonfile:
        config_data = json.load(jsonfile)

    # Initialize data store
    data_store_entity = DataStore(config_data=config_data["AreaInfo"])

    # Log file
    log_file = open('../log.txt', 'w')
    trades_text_file = open('../trades.csv', 'w')
    trades_text_file.write('period,agent,action,resource,market,quantity,price\n')



    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent] = []



    for agent in config_data["Agents"]:
        agent_type = agent["Name"]
        if agent_type == "BuildingAgent":
            agents.append(BuildingAgent(data_store_entity))
        elif agent_type == "BatteryStorageAgent":
            storage_agent = BatteryStorageAgent(data_store_entity, max_capacity=agent["Capacity"],
                                                charge_rate=agent["ChargeRate"])
            agents.append(storage_agent)
        elif agent_type == "PVAgent":
            agents.append(PVAgent(data_store_entity))
        elif agent_type == "GroceryStoreAgent":
            agents.append(GroceryStoreAgent(data_store_entity))
        elif agent_type == "ElectricityGridAgent":
            grid_agent = ElectricityGridAgent(data_store_entity, max_transfer_per_hour=agent["TransferRate"])
            agents.append(grid_agent)

    # TODO: As of right now, grid and storage agents are treated as configurable, but the code is hard coded with the
    # TODO: assumption that they'll always exist. Needs to be refactored.

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

        log_entry = 'Time period: {}, price: {}, battery charge level: {}\n'.\
            format(period, clearing_price, storage_agent.capacity)
        log_file.write(log_entry)

        # Send clearing price back to agents, allow them to "make trades", i.e. decide if they want to buy/sell
        # energy, from/to either the local market or directly from/to the external grid.
        # To be clear: These "trades" are for _actual_ amounts, not predicted. All agents except the external grid agent
        # makes these, then finally the external grid agent "fills in" the energy imbalances through "trades" of its own
        trades_excl_external = [agent.make_trade_given_clearing_price(period, clearing_price) for agent in agents]
        trades_excl_external = [i for i in trades_excl_external if i]  # filter out None
        external_trades = grid_agent.calculate_external_trades(trades_excl_external, clearing_price)
        all_trades = trades_excl_external + external_trades
        trades_text_file.write(write_rows(all_trades))
    
    # Exit gracefully
    log_file.close()
    trades_text_file.close()


if __name__ == '__main__':
    main()
