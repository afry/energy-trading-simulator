from abc import ABC, abstractmethod


class IAgent(ABC):
    """Interface for agents to implement"""

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
        # Whats the pricing logic? Always lowest possible price?

        return bids


    def make_prognosis():
        # The building should make a prognosis for how much energy will be required
        pass


class PVAgent(IAgent):
    #TODO: Implement
    def make_bid():
        # The PV park should make a bid to sell energy
        bids = []
        # Pricing logic - Highest possible price?

        return bids


    def make_prognosis():
        # The PV park should make a prognosis for how much energy will be produced
        pass


class BatteryStorageAgent(IAgent):
    def __init__(self, max_capacity = 1000):
        # Initialize with a capacity of zero
        self.capacity = 0
        # Set max capacity in kWh, default = 1000
        self.max_capacity = max_capacity


    def make_bid(self):
        # The Battery storage should generally buy if capacity is low and sell if capacity is high
        # Logic sketch:
        # 1. Start empty
        # 2. Buy until capacity exceeds some threshold
        # 3. Sell until below some other threshold
        # 4. GOTO 2
        bids = []
        # Pricing logic?

        action, quantity = self.make_prognosis(self)
        bid = Bid(action=action, quantity=quantity, price = 0) # What should price be here?
        # We need to express that the battery will buy at any price but prefers the lowest
        # And that it will buy up-to the specified amount but never more
       
        bids.append(bid)

        return bids


    def make_prognosis(self):
        # Determine if we want to sell or buy
        if self.capacity < 0.2*self.max_capacity:
            capacity_to_fill = self.max_capacity - self.capacity
            return "Buy", capacity_to_fill
        elif self.capacity > 0.8*self.max_capacity:
            return "Sell", self.capacity
            


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
    def __init__(self, action, quantity, price, resource="Electricity"):
        self.action = action
        self.resource = resource
        self.quantity = quantity
        self.price = price