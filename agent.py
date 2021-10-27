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


class PVAgent(IAgent):
    #TODO: Implement


class GridSellerAgent(IAgent):
    #TODO: Implement


class GridBuyerAgent(IAgent):
    #TODO: Implement