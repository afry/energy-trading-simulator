from abc import ABC, abstractmethod

from bid import Bid, Action, Resource
from data_store import DataStore


class IAgent(ABC):
    """Interface for agents to implement"""

    # def __init__(self):

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

        return bids

    def make_prognosis(self, period):
        # The building should make a prognosis for how much energy will be required
        pass


class PVAgent(IAgent):
    # TODO: Implement
    def make_bids(self, period):
        # The PV park should make a bid to sell energy
        bids = []

        return bids

    def make_prognosis(self, period):
        # The PV park should make a prognosis for how much energy will be produced
        pass


class BatteryStorageAgent(IAgent):

    current_charge_kwh: float  # [kWh] - should never exceed max_capacity
    max_capacity: float  # [kWh]

    def __init__(self, max_capacity, current_charge_level=0.0):
        self.max_capacity = max_capacity
        self.current_charge_level = current_charge_level

    # TODO: Implement
    def make_bids(self, period):
        # The Battery storage should generally submit two bids; buy at a low price, sell at a high price. Those prices
        # will be affected by the current_charge_kwh: Willing to buy at higher prices when current_charge_level is
        # low, and willing to sell at lower prices when current_charge_level is high.
        # To be able to implement this, the StorageAgent will need to predict what will happen to the price in coming
        # trading periods, but we will omit this for now.
        # For starters, the logic could work like this:
        # 1. Start empty
        # 2. Buy until capacity exceeds some threshold
        # 3. Sell until below some other threshold
        # 4. GOTO 2
        bids = []

        return bids

    def make_prognosis(self, period):
        # Get the current capacity of the battery storage
        pass


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
        bid_to_buy = Bid(Action.BUY, Resource.ELECTRICITY, self.MAX_TRANSFER_PER_HOUR, wholesale_price)
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

