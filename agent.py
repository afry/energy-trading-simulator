from abc import ABC, abstractmethod
import pandas as pd


class IAgent(ABC):
    """Interface for agents to implement"""

    # def __init__(self):

    @abstractmethod
    def make_bid(self, period):
        # Make a bid for produced or needed energy for next time step
        pass

    @abstractmethod
    def make_prognosis(self, period):
        # Make resource prognosis for the trading horizon
        pass


class BuildingAgent(IAgent):
    # TODO: Implement
    def make_bid(self, period):
        # The buidling should make a bid for purchasing energy
        bids = []

        return bids

    def make_prognosis(self, period):
        # The building should make a prognosis for how much energy will be required
        pass


class PVAgent(IAgent):
    # TODO: Implement
    def make_bid(self, period):
        # The PV park should make a bid to sell energy
        bids = []

        return bids

    def make_prognosis(self, period):
        # The PV park should make a prognosis for how much energy will be produced
        pass


class BatteryStorageAgent(IAgent):
    # TODO: Implement
    def make_bid(self, period):
        # The Battery storage should generally buy if capacity is low and sell if capacity is high
        # Logic sketch:
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
    nordpool_data: pd.DataFrame
    MAX_TRANSFER_PER_HOUR = 10000  # kW (placeholder value: same limit as FED)

    def __init__(self, external_price_csv='data/nordpool_area_grid_el_price.csv'):
        self.nordpool_data = pd.read_csv(external_price_csv, index_col=0)
        if self.nordpool_data.mean()[0] > 100:
            # convert price from SEK per MWh to SEK per kWh
            self.nordpool_data = self.nordpool_data / 1000
        self.nordpool_data.columns = ['price_sek_kwh']

    def make_bid(self, period):
        # Submit 2 bids here
        # Sell up to MAX_TRANSFER_PER_HOUR kWh at calculate_retail_price(period)
        # Buy up to MAX_TRANSFER_PER_HOUR kWh at calculate_wholesale_price(period)
        # TODO: Build bid
        bids = []

        return bids

    def calculate_retail_price(self, period):
        """Returns the price at which the agent is willing to sell electricity, in SEK/kWh"""
        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        return self.nordpool_data.loc[period].iloc[0] + 0.48

    def calculate_wholesale_price(self, period):
        """Returns the price at which the agent is willing to buy electricity, in SEK/kWh"""
        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        return self.nordpool_data.loc[period].iloc[0] + 0.05

    def make_prognosis(self, period):
        # Not sure what this method should return
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