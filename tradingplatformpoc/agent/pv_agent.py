import datetime
from typing import Any, Dict, List, Tuple, Union

from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_selling
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.trading_platform_utils import minus_n_hours


class PVAgent(IAgent):
    electricity_pricing: ElectricityPrice

    def __init__(self, electricity_pricing: ElectricityPrice,
                 digital_twin: StaticDigitalTwin, guid="PVAgent"):
        super().__init__(guid)
        self.electricity_pricing = electricity_pricing
        self.digital_twin = digital_twin

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None) -> List[GrossBid]:
        # The PV park should make a bid to sell energy
        # Pricing logic:
        # If the agent represents only solar panels and no storage, then the electricity must be sold.
        # However, the agent could always sell to the external grid, if the local price is too low.
        prognosis = self.make_prognosis(period, Resource.ELECTRICITY)
        if prognosis > 0:
            return [self.construct_elec_bid(period, Action.SELL, prognosis,
                                            self.electricity_pricing.get_external_grid_buy_price(period))]
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
            wholesale_price = self.electricity_pricing.get_external_grid_buy_price(period)
            clearing_price = clearing_prices[Resource.ELECTRICITY]
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(
                clearing_price, wholesale_price, True)
            tax = self.electricity_pricing.get_tax(market_to_use)
            grid_fee = self.electricity_pricing.get_grid_fee(market_to_use)
            return [self.construct_elec_trade(period=period, action=Action.SELL, quantity=-usage,
                                              price=price_to_use, market=market_to_use,
                                              tax_paid=tax, grid_fee_paid=grid_fee)], {}
        else:
            return [], {}
