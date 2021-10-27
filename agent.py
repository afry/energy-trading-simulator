from abc import ABC, abstractmethod


class IAgent(ABC):
    """Interface for agents to implement"""
    def __init__(self, type, production, consumption):
        self.type = type
        self.production = production
        self.consumpton = consumption
    
    @abstractmethod
    def make_bid():
        # Make a bid for produced or needed energy for next time step
        pass
    

    def make_prognosis():
        # Make resource prognosis for the trading horizon
        pass

class BuildingAgent(IAgent):
    #TODO: Implement
    def make_bid():
        # The buidling should make a bid for purchasing energy
        pass


    def make_prognosis():
        # The building should make a prognosis for how much energy will be required
        pass


class PVAgent(IAgent):
    #TODO: Implement
    def make_bid():
        # The PV park should make a bid to sell energy
        pass


    def make_prognosis():
        # The PV park should make a prognosis for how much energy will be produced
        pass


# Grid seller and buyer should perhaps not implement the agent interface, but rather something else?
class GridSellerAgent(IAgent):
    #TODO: Implement
    def make_bid():
        pass


    def make_prognosis():
        pass


class GridBuyerAgent(IAgent):
    #TODO: Implement
    def make_bid():
        pass


    def make_prognosis():
        pass