from abc import ABC, abstractmethod
import math

import bid
from bid import Bid, Action, Resource
from data_store import DataStore
from trade import Trade, Market


class IAgent(ABC):
    """Interface for agents to implement"""

    def __init__(self, guid: str):
        self.guid = guid

    @abstractmethod
    def make_bids(self, period):
        # Make a bid for produced or needed energy for next time step
        pass

    @abstractmethod
    def make_prognosis(self, period):
        # Make resource prognosis for the trading horizon
        pass

    @abstractmethod
    def get_actual_usage(self, period):
        # Return actual resource usage/supply for the trading horizon
        # If negative, it means the agent was a net-producer for the trading period
        pass

    @abstractmethod
    def make_trade_given_clearing_price(self, period, clearing_price):
        # Once market solver has decided a clearing price, it will send it to the agents with this method
        # Should return a Trade
        pass

    def construct_bid(self, action, resource, quantity, price):
        return Bid(action, resource, quantity, price, self.guid)

    def construct_trade(self, action, resource, quantity, price, market, period):
        return Trade(action, resource, quantity, price, self.guid, market, period)


class BuildingAgent(IAgent):

    def __init__(self, data_store: DataStore, guid="BuildingAgent"):
        super().__init__(guid)
        self.data_store = data_store

    def make_bids(self, period):
        # The building should make a bid for purchasing energy
        bids = [self.construct_bid(Action.BUY, Resource.ELECTRICITY, self.make_prognosis(period), math.inf)]
        # This demand must be fulfilled - therefore price is inf
        return bids

    def make_prognosis(self, period):
        # The building should make a prognosis for how much energy will be required
        electricity_demand = self.data_store.get_tornet_household_electricity_consumed(period)
        # FUTURE: Make a prognosis, instead of using the actual
        return electricity_demand

    def get_actual_usage(self, period):
        actual_usage = self.data_store.get_tornet_household_electricity_consumed(period)
        return actual_usage

    def make_trade_given_clearing_price(self, period, clearing_price):
        retail_price = self.data_store.get_retail_price(period)
        price_to_use, market_to_use = get_price_and_market_to_use_when_buying(clearing_price, retail_price)
        return self.construct_trade(Action.BUY, Resource.ELECTRICITY, self.get_actual_usage(period), price_to_use,
                                    market_to_use, period)


class GroceryStoreAgent(IAgent):
    """Currently very similar to BuildingAgent. May in the future sell excess heat."""

    def __init__(self, data_store: DataStore, guid="GroceryStoreAgent"):
        super().__init__(guid)
        self.data_store = data_store

    def make_bids(self, period):
        # The building should make a bid for purchasing energy
        electricity_needed = self.make_prognosis(period)
        bids = []
        if electricity_needed > 0:
            bids.append(self.construct_bid(Action.BUY, Resource.ELECTRICITY, electricity_needed, math.inf))
            # This demand must be fulfilled - therefore price is inf
        elif electricity_needed < 0:
            bids.append(self.construct_bid(Action.SELL, Resource.ELECTRICITY, -electricity_needed, 0))
            # If the store doesn't have it's own battery, then surplus electricity must be sold, so price is 0
        return bids

    def make_prognosis(self, period):
        # The building should make a prognosis for how much energy will be required.
        # If negative, it means there is a surplus
        electricity_demand = self.data_store.get_coop_electricity_consumed(period)
        electricity_supply = self.data_store.get_coop_pv_produced(period)
        # FUTURE: Make a prognosis, instead of using the actual
        return electricity_demand - electricity_supply

    def get_actual_usage(self, period):
        electricity_demand = self.data_store.get_coop_electricity_consumed(period)
        electricity_supply = self.data_store.get_coop_pv_produced(period)
        return electricity_demand - electricity_supply

    def make_trade_given_clearing_price(self, period, clearing_price):
        retail_price = self.data_store.get_retail_price(period)
        wholesale_price = self.data_store.get_wholesale_price(period)
        usage = self.get_actual_usage(period)
        if usage >= 0:
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(clearing_price, retail_price)
            return self.construct_trade(Action.BUY, Resource.ELECTRICITY, usage, price_to_use, market_to_use, period)
        else:
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(clearing_price, wholesale_price)
            return self.construct_trade(Action.SELL, Resource.ELECTRICITY, usage, price_to_use, market_to_use, period)


class PVAgent(IAgent):

    def __init__(self, data_store: DataStore, guid="PVAgent"):
        super().__init__(guid)
        self.data_store = data_store

    def make_bids(self, period):
        # The PV park should make a bid to sell energy
        # Pricing logic:
        # If the agent represents only solar panels and no storage, then the electricity must be sold.
        # However, the agent could always sell to the external grid, if the local price is too low.
        prognosis = self.make_prognosis(period)
        if prognosis > 0:
            return [self.construct_bid(Action.SELL,
                                       Resource.ELECTRICITY,
                                       prognosis,
                                       self.get_external_grid_buy_price(period))]
        else:
            return []

    def make_prognosis(self, period):
        # The PV park should make a prognosis for how much energy will be produced
        # FUTURE: Make a prognosis, instead of using the actual
        return self.data_store.get_tornet_pv_produced(period)

    def get_external_grid_buy_price(self, period):
        wholesale_price = self.data_store.get_wholesale_price(period)

        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325, Varberg Energi can pay an extra
        # remuneration on top of the Nordpool spot price. This can vary, "depending on for example membership".
        # Might make sense to make this number configurable.
        remuneration_modifier = 0

        return wholesale_price + remuneration_modifier

    def get_actual_usage(self, period):
        # Negative means net producer
        return -self.data_store.get_tornet_pv_produced(period)

    def make_trade_given_clearing_price(self, period, clearing_price):
        usage = self.get_actual_usage(period)
        if usage < 0:
            wholesale_price = self.get_external_grid_buy_price(period)
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(clearing_price, wholesale_price)
            return self.construct_trade(Action.SELL, Resource.ELECTRICITY, usage, price_to_use,
                                        market_to_use, period)
        else:
            return None


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


class ElectricityGridAgent(IAgent):
    MAX_TRANSFER_PER_HOUR = 10000  # kW (placeholder value: same limit as FED)

    def __init__(self, data_store: DataStore, guid="ElectricityGridAgent"):
        super().__init__(guid)
        self.data_store = data_store

    def make_bids(self, period):
        # Submit 2 bids here
        # Sell up to MAX_TRANSFER_PER_HOUR kWh at calculate_retail_price(period)
        # Buy up to MAX_TRANSFER_PER_HOUR kWh at calculate_wholesale_price(period)
        retail_price = self.data_store.get_retail_price(period)
        wholesale_price = self.data_store.get_wholesale_price(period)
        bid_to_sell = self.construct_bid(Action.SELL, Resource.ELECTRICITY, self.MAX_TRANSFER_PER_HOUR, retail_price)
        bid_to_buy = self.construct_bid(action=Action.BUY,
                                        resource=Resource.ELECTRICITY,
                                        quantity=self.MAX_TRANSFER_PER_HOUR,
                                        price=wholesale_price)
        bids = [bid_to_sell, bid_to_buy]
        return bids

    def make_prognosis(self, period):
        # FUTURE: Make prognoses of the price, instead of using actual? Although we are already using the day-ahead?
        pass

    def get_actual_usage(self, period):
        pass

    def make_trade_given_clearing_price(self, period, clearing_price):
        # The external grid is used to make up for any differences on the local market. Therefore these will be
        # calculated at a later stage (in calculate_external_trades)
        pass

    def calculate_external_trades(self, trades_excl_external, local_clearing_price):
        trades_to_add = []

        periods = set([trade.period for trade in trades_excl_external])
        for period in periods:
            trades_for_this_period = [trade for trade in trades_excl_external if trade.period == period]
            retail_price = self.data_store.get_retail_price(period)
            wholesale_price = self.data_store.get_wholesale_price(period)

            resource = Resource.ELECTRICITY  # FUTURE: Go through HEATING and maybe COOLING as well
            trades_for_this_resource = [trade for trade in trades_for_this_period if trade.resource == resource]
            self.calculate_external_trades_for_resource_and_market(Market.LOCAL, period, resource, retail_price,
                                                                   trades_for_this_resource, trades_to_add,
                                                                   wholesale_price, local_clearing_price)
            self.calculate_external_trades_for_resource_and_market(Market.EXTERNAL, period, resource, retail_price,
                                                                   trades_for_this_resource, trades_to_add,
                                                                   wholesale_price, local_clearing_price)
        return trades_to_add

    def calculate_external_trades_for_resource_and_market(self, market, period, resource, retail_price,
                                                          trades_for_this_resource, trades_to_add, wholesale_price,
                                                          local_clearing_price):
        trades_for_this_resource_and_market = [trade for trade in trades_for_this_resource if trade.market == market]
        sum_buys = sum([trade.quantity for trade in trades_for_this_resource_and_market if trade.action == Action.BUY])
        sum_sells = sum(
            [trade.quantity for trade in trades_for_this_resource_and_market if trade.action == Action.SELL])
        if sum_buys > sum_sells:
            trades_to_add.append(
                Trade(Action.SELL, resource, sum_buys - sum_sells, retail_price, self.guid, market, period))
            if market == Market.LOCAL:
                if local_clearing_price < retail_price:
                    # This isn't necessarily a problem, per se, but when we move away from perfect predictions,
                    # we'll have to do something when this happens: Basically the market solver believed that locally
                    # produced energy would cover the needs of all agents, but it turned out to not be the case,
                    # so we had to import some energy from the external grid, at a higher price than the local price.
                    # The agents will have to split the extra cost between themselves, in some way. Both producers and
                    # consumers could be to blame - producers may have produced less than they thought they would, and
                    # consumers may have consumed more than they thought they would. We'll have to work out some
                    # proportional way of distributing the extra cost.
                    raise RuntimeWarning("Warning: External grid sells at {} SEK/kWh to the local market, but the "
                                         "clearing price was {}".format(retail_price, local_clearing_price))
                elif local_clearing_price > retail_price:
                    raise RuntimeError("Unexpected result: Local clearing price higher than external retail price")
        elif sum_buys < sum_sells:
            trades_to_add.append(
                Trade(Action.BUY, resource, sum_sells - sum_buys, wholesale_price, self.guid, market, period))
            if market == Market.LOCAL:
                if local_clearing_price > wholesale_price:
                    # This isn't necessarily a problem, per se, but when we move away from perfect predictions,
                    # we'll have to do something when this happens: Basically the market solver believed that there
                    # would be a local deficit, but it turned out to not be the case, instead there was a local
                    # surplus. So, producing agents had to export some energy to the external grid, at a lower price
                    # than the local price. The agents will have to split the extra cost (or rather, missing revenue)
                    # between themselves, in some way. Both producers and consumers could be to blame - producers may
                    # have produced more than they thought they would, and consumers may have consumed less than they
                    # thought they would. We'll have to work out some proportional way of distributing the extra cost.
                    raise RuntimeWarning("Warning: External grid buys at {} SEK/kWh from the local market, but the "
                                         "clearing price was {}". format(wholesale_price, local_clearing_price))
                elif local_clearing_price < wholesale_price:
                    raise RuntimeError("Unexpected result: Local clearing price lower than external wholesale price")


def get_price_and_market_to_use_when_buying(clearing_price, retail_price):
    if clearing_price <= retail_price:
        return clearing_price, Market.LOCAL
    else:
        return retail_price, Market.EXTERNAL


def get_price_and_market_to_use_when_selling(clearing_price, wholesale_price):
    if clearing_price >= wholesale_price:
        return clearing_price, Market.LOCAL
    else:
        return wholesale_price, Market.EXTERNAL