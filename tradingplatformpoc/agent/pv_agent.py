import datetime
from typing import Any, Dict, List, Tuple, Union

from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_selling
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Trade, TradeMetadataKey
from tradingplatformpoc.trading_platform_utils import minus_n_hours


class PVAgent(IAgent):

    def __init__(self, data_store: DataStore, digital_twin: StaticDigitalTwin, guid="PVAgent"):
        super().__init__(guid, data_store)
        self.digital_twin = digital_twin

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None) -> List[GrossBid]:
        # The PV park should make a bid to sell energy
        # Pricing logic:
        # If the agent represents only solar panels and no storage, then the electricity must be sold.
        # However, the agent could always sell to the external grid, if the local price is too low.
        prognosis = self.make_prognosis(period, Resource.ELECTRICITY)
        if prognosis > 0:
            return [self.construct_elec_bid(Action.SELL, prognosis,
                                            self.get_external_grid_buy_price(period, Resource.ELECTRICITY))]
        else:
            return []

    def make_prognosis(self, period: datetime.datetime, resource: Resource) -> float:
        # The PV park should make a prognosis for how much energy will be produced
        prev_trading_period = minus_n_hours(period, 1)
        try:
            electricity_prod_prev = self.digital_twin.get_production(prev_trading_period, Resource.ELECTRICITY)
        except KeyError:
            # First time step, haven't got a previous value to use. Will go with a perfect prediction here
            electricity_prod_prev = self.digital_twin.get_production(period, Resource.ELECTRICITY)
        return electricity_prod_prev

    def get_actual_usage(self, period: datetime.datetime, resource: Resource) -> float:
        # Negative means net producer
        return -self.digital_twin.get_production(period, Resource.ELECTRICITY)

    def make_trades_given_clearing_price(self, period: datetime.datetime, clearing_prices: Dict[Resource, float],
                                         accepted_bids_for_agent: List[NetBidWithAcceptanceStatus]) -> \
            Tuple[List[Trade], Dict[TradeMetadataKey, Any]]:
        usage = self.get_actual_usage(period, Resource.ELECTRICITY)
        if usage < 0:
            wholesale_price = self.get_external_grid_buy_price(period, Resource.ELECTRICITY)
            clearing_price = clearing_prices[Resource.ELECTRICITY]
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(clearing_price, wholesale_price)
            # NOTE: Here we assume that even if we sell electricity on the "external market", we still pay
            # the internal electricity tax, and the internal grid fee
            return [self.construct_elec_trade(Action.SELL, -usage, price_to_use, market_to_use, period,
                                              tax_paid=self.data_store.elec_tax_internal,
                                              grid_fee_paid=self.data_store.elec_grid_fee_internal)], {}
        else:
            return [], {}
