from abc import ABC, abstractmethod


class IAgent(ABC):
    """Interface for agents to implement"""
    def __init__(self, type, production, consumption):
        # What kind of state data should an agent keep? Any at all?
        self.type = type
        self.production = production
        self.consumpton = consumption
    

    @abstractmethod
    def make_bid():
        # Make a bid for produced or needed energy for next time step
        pass
    

    @abstractmethod
    def make_prognosis():
        # Make resource prognosis for the trading horizon
        pass


class BuildingAgent(IAgent):
    #TODO: Implement
    def make_bid():
        # The buidling should make a bid for purchasing energy
        bids = []

        return bids


    def make_prognosis():
        # The building should make a prognosis for how much energy will be required
        pass


class PVAgent(IAgent):
    #TODO: Implement
    def make_bid():
        # The PV park should make a bid to sell energy
        bids = []

        return bids


    def make_prognosis():
        # The PV park should make a prognosis for how much energy will be produced
        pass


class BatteryStorageAgent(IAgent):
    #TODO: Implement
    def make_bid():
        # The Battery storage should generally buy if capacity is low and sell if capacity is high
        # Logic sketch:
        # 1. Start empty
        # 2. Buy until capacity exceeds some threshold
        # 3. Sell until below some other threshold
        # 4. GOTO 2
        bids = []

        return bids


    def make_prognosis():
        # Get the current capacity of the battery storage
        pass


class GridAgent(IAgent):
    #TODO: Implement
    def make_bid():
        # Always make one bid to buy at wholesale price, and one bid to sell att market price
        bids = []

        return bids


    def make_prognosis():
        # Get the grid selling price
        pass


class Bid():
    """The bid model for our trading platform.
    
    Parameters:
        Action: Buy/sell
        Resource: Electricity
        Quantity: Amount in kWh
        Price: SEK/kWh
    """
    def __init__(self, action, resource, quantity, price):
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price