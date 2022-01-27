import datetime
from typing import List, Union

from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_selling
from tradingplatformpoc.bid import Action, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.trade import Trade
from tradingplatformpoc.trading_platform_utils import minus_n_hours


class PVAgent(IAgent):

    def __init__(self, data_store: DataStore, digital_twin: StaticDigitalTwin, guid="PVAgent"):
        super().__init__(guid, data_store)
        self.digital_twin = digital_twin

    def make_bids(self, period: datetime.datetime, clearing_prices_dict: Union[dict, None] = None):
        # The PV park should make a bid to sell energy
        # Pricing logic:
        # If the agent represents only solar panels and no storage, then the electricity must be sold.
        # However, the agent could always sell to the external grid, if the local price is too low.
        prognosis = self.make_prognosis(period, Resource.ELECTRICITY)
        if prognosis > 0:
            return [self.construct_bid(Action.SELL,
                                       Resource.ELECTRICITY,
                                       prognosis,
                                       self.get_external_grid_buy_price(period, Resource.ELECTRICITY))]
        else:
            return []

    def make_prognosis(self, period: datetime.datetime, resource: Resource):
        # The PV park should make a prognosis for how much energy will be produced
        prev_trading_period = minus_n_hours(period, 1)
        try:
            electricity_prod_prev = self.digital_twin.get_production(prev_trading_period, Resource.ELECTRICITY)
        except KeyError:
            # First time step, haven't got a previous value to use. Will go with a perfect prediction here
            electricity_prod_prev = self.digital_twin.get_production(period, Resource.ELECTRICITY)
        return electricity_prod_prev

    def get_actual_usage(self, period: datetime.datetime, resource: Resource):
        # Negative means net producer
        return -self.digital_twin.get_production(period, Resource.ELECTRICITY)

    def make_trades_given_clearing_price(self, period: datetime.datetime, clearing_price: float,
                                         clearing_prices_dict: dict,
                                         accepted_bids_for_agent: List[BidWithAcceptanceStatus]) -> List[Trade]:
        usage = self.get_actual_usage(period, Resource.ELECTRICITY)
        if usage < 0:
            wholesale_price = self.get_external_grid_buy_price(period, Resource.ELECTRICITY)
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(clearing_price, wholesale_price)
            return [self.construct_trade(Action.SELL, Resource.ELECTRICITY, -usage, price_to_use,
                                         market_to_use, period)]
        else:
            return []
