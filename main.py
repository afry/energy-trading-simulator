from typing import List
from agent import IAgent
from agent import BuildingAgent
from agent import PVAgent
from agent import GroceryStoreAgent
from agent import BatteryStorageAgent
from agent import ElectricityGridAgent
from bid import Bid, Action
from market_solver import MarketSolver
from data_store import DataStore
from trade import write_rows


def main():
    """The core loop of the simulation, running through the desired time period and performing trades."""

    # Log file
    log_file = open('log.txt', 'w')
    trades_text_file = open('trades.csv', 'w')

    # Initialize data store
    data_store_entity = DataStore('data/nordpool_area_grid_el_price.csv',
                                  'data/full_mock_energy_data.csv')

    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent] = []

    agents.append(BuildingAgent(data_store_entity))
    storage_agent = BatteryStorageAgent()
    agents.append(storage_agent)
    agents.append(PVAgent(data_store_entity))
    agents.append(GroceryStoreAgent(data_store_entity))
    grid_agent = ElectricityGridAgent(data_store_entity)
    agents.append(grid_agent)

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
