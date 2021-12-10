from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_selling
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.trading_platform_utils import minus_n_hours


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
        prev_trading_period = minus_n_hours(period, 1)
        try:
            electricity_prod_prev = self.data_store.get_tornet_pv_produced(prev_trading_period)
        except KeyError:
            # First time step, haven't got a previous value to use. Will go with a perfect prediction here
            electricity_prod_prev = self.data_store.get_tornet_pv_produced(period)
        return electricity_prod_prev

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
            return self.construct_trade(Action.SELL, Resource.ELECTRICITY, -usage, price_to_use,
                                        market_to_use, period)
        else:
            return None
