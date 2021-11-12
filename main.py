from typing import List
from agent import IAgent
from agent import BuildingAgent
from agent import PVAgent
from agent import GroceryStoreAgent
from agent import BatteryStorageAgent
from agent import ElectricityGridAgent
from bid import Bid
from market_solver import MarketSolver
from data_store import DataStore


def main():
    """The core loop of the simulation, running through the desired time period and performing trades."""

    # Log file
    log_file = open('log.txt', 'w')

    # Initialize data store
    data_store_entity = DataStore('data/nordpool_area_grid_el_price.csv',
                                  'data/full_mock_energy_data.csv')

    # Register all agents
    # Keep a list of all agents to iterate over later
    agents: List[IAgent] = []

    agents.append(BuildingAgent(data_store_entity))
    agents.append(BatteryStorageAgent())
    agents.append(PVAgent(data_store_entity))
    agents.append(GroceryStoreAgent(data_store_entity))
    agents.append(ElectricityGridAgent(data_store_entity))

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
            result = market_solver.resolve_bids(bids_flat)
        except RuntimeError as e:
            result = e.args
        # What do we do with results? Do we feed them back do the agents? Needs a method in the interface.
        log_entry = 'Time period: {}, price: {} \n'.format(period, result)
        log_file.write(log_entry)
    
    # Exit gracefully
    log_file.close()


if __name__ == '__main__':
    main()
