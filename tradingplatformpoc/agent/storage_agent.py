import math

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.trade import Market


class BatteryStorageAgent(IAgent):
    """The agent for a battery storage actor.

    The battery works on the logic that it tries to keep it capacity between an upper and a lower bound, 80% and 20%
    for instance. Starting empty, the battery will charge until at or above the upper threshold. It will then
    discharge until at or below the lower threshold.
    """

    def __init__(self, data_store: DataStore, digital_twin: StorageDigitalTwin, guid="BatteryStorageAgent"):
        super().__init__(guid)
        self.data_store = data_store
        self.digital_twin = digital_twin
        # Upper and lower thresholds
        self.upper_threshold = 0.8
        self.lower_threshold = 0.2
        # A state used to check whether filling or emptying capacity - to be removed when this logic changes
        self.charging = True

    def make_bids(self, period):
        bids = []

        action, quantity = self.make_prognosis(self)
        if action is Action.BUY:
            price = math.inf  # Inf as upper bound for buying price
        elif action is Action.SELL:
            # Wants at least the external wholesale price, if local price would be lower than that,
            # the agent would just sell directly to external
            price = self.data_store.get_wholesale_price(period)
        bid = self.construct_bid(action=action,
                                 quantity=quantity,
                                 price=price,
                                 resource=Resource.ELECTRICITY)  # What should price be here?
        # We need to express that the battery will buy at any price but prefers the lowest
        # And that it will buy up-to the specified amount but never more

        bids.append(bid)

        return bids

    def make_prognosis(self, period):
        # Determine if we want to sell or buy
        if self.digital_twin.capacity_kwh < self.lower_threshold * self.digital_twin.max_capacity_kwh:
            self.charging = True
        elif self.digital_twin.capacity_kwh > self.upper_threshold * self.digital_twin.max_capacity_kwh:
            self.charging = False

        if self.charging:
            capacity_to_charge = self.digital_twin.get_possible_charge_amount()
            return Action.BUY, capacity_to_charge
        else:
            capacity_to_deliver = self.digital_twin.get_possible_discharge_amount()
            return Action.SELL, capacity_to_deliver

    def get_actual_usage(self, period):
        pass

    def make_trade_given_clearing_price(self, period, clearing_price):
        # In this implementation, the battery never sells or buys directly from the external grid.
        action, quantity = self.make_prognosis(self)
        if action == Action.BUY:
            actual_charge_quantity = self.digital_twin.charge(quantity)
            return self.construct_trade(Action.BUY, Resource.ELECTRICITY, actual_charge_quantity, clearing_price,
                                        Market.LOCAL, period)
        else:
            actual_discharge_quantity = self.digital_twin.discharge(quantity)
            return self.construct_trade(Action.SELL, Resource.ELECTRICITY, actual_discharge_quantity, clearing_price,
                                        Market.LOCAL, period)