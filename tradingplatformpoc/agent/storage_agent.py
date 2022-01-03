import numpy as np

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.trade import Market


class StorageAgent(IAgent):
    """The agent for a battery storage actor.

    The battery works on the logic that it tries to keep it capacity between an upper and a lower bound, 80% and 20%
    for instance. Starting empty, the battery will charge until at or above the upper threshold. It will then
    discharge until at or below the lower threshold.
    """

    def __init__(self, data_store: DataStore, digital_twin: StorageDigitalTwin, guid="StorageAgent"):
        super().__init__(guid, data_store)
        self.digital_twin = digital_twin
        self.go_back_n_hours = 24 * 7
        # Upper and lower thresholds
        self.if_lower_than_this_percentile_then_buy = 20
        self.if_higher_than_this_percentile_then_sell = 80

    def make_bids(self, period):
        nordpool_prices_last_n_hours = self.data_store.get_nordpool_prices_last_n_hours(period, self.go_back_n_hours)
        buy_bid = self.construct_bid(action=Action.BUY,
                                     quantity=self.calculate_buy_quantity(),
                                     price=self.calculate_buy_price(nordpool_prices_last_n_hours),
                                     resource=Resource.ELECTRICITY)
        sell_bid = self.construct_bid(action=Action.SELL,
                                      quantity=self.calculate_sell_quantity(),
                                      price=self.calculate_sell_price(nordpool_prices_last_n_hours),
                                      resource=Resource.ELECTRICITY)
        return [buy_bid, sell_bid]

    def make_prognosis(self, period):
        pass

    def get_actual_usage(self, period):
        pass

    def make_trade_given_clearing_price(self, period, clearing_price):
        # The following is only needed since we have to calculate ourselves what bid(s) were accepted
        nordpool_prices_last_n_hours = self.data_store.get_nordpool_prices_last_n_hours(period, self.go_back_n_hours)
        current_nordpool_wholesale_price = self.data_store.get_wholesale_price(period)
        current_nordpool_retail_price = self.data_store.get_retail_price(period)
        buy_bid_price = min(self.calculate_buy_price(nordpool_prices_last_n_hours), current_nordpool_retail_price)
        sell_bid_price = max(self.calculate_sell_price(nordpool_prices_last_n_hours), current_nordpool_wholesale_price)
        buy_bid_quantity = self.calculate_buy_quantity()
        sell_bid_quantity = self.calculate_sell_quantity()
        # In this implementation, the battery never sells or buys directly from the external grid.

        if clearing_price <= buy_bid_price:
            actual_charge_quantity = self.digital_twin.charge(buy_bid_quantity)
            if actual_charge_quantity > 0:
                return self.construct_trade(Action.BUY, Resource.ELECTRICITY, actual_charge_quantity,
                                            clearing_price, Market.LOCAL, period)
        elif clearing_price >= sell_bid_price:
            actual_discharge_quantity = self.digital_twin.discharge(sell_bid_quantity)
            if actual_discharge_quantity > 0:
                return self.construct_trade(Action.SELL, Resource.ELECTRICITY, actual_discharge_quantity,
                                            clearing_price, Market.LOCAL, period)
        return None

    def calculate_buy_price(self, nordpool_prices_last_n_hours):
        return np.percentile(nordpool_prices_last_n_hours, self.if_lower_than_this_percentile_then_buy)

    def calculate_sell_price(self, nordpool_prices_last_n_hours):
        return np.percentile(nordpool_prices_last_n_hours, self.if_higher_than_this_percentile_then_sell)

    def calculate_buy_quantity(self):
        """Will buy 50% of remaining empty space, but not more than the digital twin's charge limit"""
        empty_capacity_kwh = self.digital_twin.max_capacity_kwh - self.digital_twin.capacity_kwh
        return min([empty_capacity_kwh / 2.0, self.digital_twin.charge_limit_kwh])

    def calculate_sell_quantity(self):
        """Will sell 50% of current charge level, but not more than the digital twin's discharge limit"""
        return min([self.digital_twin.capacity_kwh / 2.0, self.digital_twin.discharge_limit_kwh])
