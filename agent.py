from abc import ABC, abstractmethod
import math

from bid import Bid, Action, Resource
from data_store import DataStore


class IAgent(ABC):
    """Interface for agents to implement"""

    @abstractmethod
    def make_bids(self, period):
        # Make a bid for produced or needed energy for next time step
        pass

    @abstractmethod
    def make_prognosis(self, period):
        # Make resource prognosis for the trading horizon
        pass


class BuildingAgent(IAgent):
    # TODO: Implement
    def make_bids(self, period):
        # The buidling should make a bid for purchasing energy
        bids = []
        # Whats the pricing logic? Always lowest possible price?

        return bids

    def make_prognosis(self, period):
        # The building should make a prognosis for how much energy will be required
        pass


class PVAgent(IAgent):
    # TODO: Implement
    def make_bids(self, period):
        # The PV park should make a bid to sell energy
        bids = []
        # Pricing logic - Highest possible price?

        return bids

    def make_prognosis(self, period):
        # The PV park should make a prognosis for how much energy will be produced
        pass


class BatteryStorageAgent(IAgent):
    """The agent for a battery storage actor.
    
    The battery works on the logic that it tries to keep it capacity between an upper and a lower bound, 80% and 20%
    for instance. Starting empty, the battery will charge until at or above the upper threshold. It will then
    discharge until at or below the lower threshold.
    """

    def __init__(self, max_capacity=1000):
        # Initialize with a capacity of zero
        self.capacity = 0
        # Set max capacity in kWh, default = 1000
        self.max_capacity = max_capacity
        # A state used to check whether filling or emptying capacity
        self.charging = True
        # Upper and lower thresholds
        self.upper_threshold = 0.8
        self.lower_threshold = 0.2
        # Maximum charge per time step
        self.charge_limit = self.max_capacity * 0.1

    def make_bids(self, period):
        bids = []

        action, quantity = self.make_prognosis(self)
        if action is Action.BUY:
            price = math.inf  # Inf as upper bound for buying price
        elif action is Action.SELL:
            price = 0.0
        bid = Bid(action=action,
                  quantity=quantity,
                  price=price,
                  resource=Resource.ELECTRICITY)  # What should price be here?
        # We need to express that the battery will buy at any price but prefers the lowest
        # And that it will buy up-to the specified amount but never more

        bids.append(bid)

        return bids

    def make_prognosis(self, period):
        # Determine if we want to sell or buy
        if self.capacity < self.lower_threshold * self.max_capacity:
            self.charging = True
        elif self.capacity > self.upper_threshold * self.max_capacity:
            self.charging = False

        if self.charging:
            capacity_to_charge = min([self.max_capacity - self.capacity, self.charge_limit])
            return Action.BUY, capacity_to_charge
        else:
            capacity_to_deliver = min([self.capacity, self.charge_limit])
            return Action.SELL, capacity_to_deliver

    # TODO: Need a method to change the current charge level, based on market solver output


class ElectricityGridAgent(IAgent):
    MAX_TRANSFER_PER_HOUR = 10000  # kW (placeholder value: same limit as FED)

    def __init__(self, data_store: DataStore):
        self.data_store = data_store

    def make_bids(self, period):
        # Submit 2 bids here
        # Sell up to MAX_TRANSFER_PER_HOUR kWh at calculate_retail_price(period)
        # Buy up to MAX_TRANSFER_PER_HOUR kWh at calculate_wholesale_price(period)
        retail_price = self.calculate_retail_price(period)
        wholesale_price = self.calculate_wholesale_price(period)
        bid_to_sell = Bid(Action.SELL, Resource.ELECTRICITY, self.MAX_TRANSFER_PER_HOUR, retail_price)
        bid_to_buy = Bid(action=Action.BUY,
                         resource=Resource.ELECTRICITY,
                         quantity=self.MAX_TRANSFER_PER_HOUR,
                         price=wholesale_price)
        bids = [bid_to_sell, bid_to_buy]
        return bids

    def calculate_retail_price(self, period):
        """Returns the price at which the agent is willing to sell electricity, in SEK/kWh"""
        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        return self.data_store.get_nordpool_price_for_period(period) + 0.48

    def calculate_wholesale_price(self, period):
        """Returns the price at which the agent is willing to buy electricity, in SEK/kWh"""
        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        return self.data_store.get_nordpool_price_for_period(period) + 0.05

    def make_prognosis(self, period):
        # Not sure what this method should return
        pass
