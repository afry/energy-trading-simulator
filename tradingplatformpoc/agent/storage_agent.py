import math

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.trade import Market


class BatteryStorageAgent(IAgent):
    """The agent for a battery storage actor.

    The battery works on the logic that it tries to keep it capacity between an upper and a lower bound, 80% and 20%
    for instance. Starting empty, the battery will charge until at or above the upper threshold. It will then
    discharge until at or below the lower threshold.
    """

    def __init__(self, max_capacity=1000, guid="BatteryStorageAgent"):
        super().__init__(guid)
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

    def get_actual_usage(self, period):
        pass

    def make_trade_given_clearing_price(self, period, clearing_price):
        # In this implementation, the battery never sells or buys directly from the external grid.
        action, quantity = self.make_prognosis(self)
        if action == Action.BUY:
            actual_charge_quantity = self.charge(quantity)
            return self.construct_trade(Action.BUY, Resource.ELECTRICITY, actual_charge_quantity, clearing_price,
                                        Market.LOCAL, period)
        else:
            actual_discharge_quantity = self.discharge(quantity)
            return self.construct_trade(Action.SELL, Resource.ELECTRICITY, actual_discharge_quantity, clearing_price,
                                        Market.LOCAL, period)

    def charge(self, quantity):
        """Charges the battery, changing the fields "charging" and "capacity".
        Will return how much the battery was charged. This will most often be equal to the "quantity" argument, but will
        be adjusted for "max_capacity" and "charge_limit".
        """
        self.charging = True
        # So that we don't exceed max capacity:
        amount_to_charge = min(float(self.max_capacity - self.capacity), float(quantity), self.charge_limit)
        self.capacity = self.capacity + amount_to_charge
        return amount_to_charge

    def discharge(self, quantity):
        """Discharges the battery, changing the fields "charging" and "capacity".
        Will return how much the battery was discharged. This will most often be equal to the "quantity" argument, but
        will be adjusted for current "capacity" and "charge_limit".
        """
        self.charging = False
        # So that we don't discharge more than self.capacity:
        amount_to_discharge = min(max(float(self.capacity), float(quantity)), self.charge_limit)
        self.capacity = self.capacity - amount_to_discharge
        return amount_to_discharge