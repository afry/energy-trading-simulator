import datetime
import logging
from typing import Any, Dict, Iterable, List, Tuple, Union

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Market, Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice

logger = logging.getLogger(__name__)


class GridAgent(IAgent):
    resource: Resource
    max_transfer_per_hour: float
    pricing: Union[HeatingPrice, ElectricityPrice]

    def __init__(self, pricing: Union[HeatingPrice, ElectricityPrice], resource: Resource,
                 max_transfer_per_hour=10000, guid="GridAgent"):
        super().__init__(guid)
        self.resource = resource
        self.pricing = self._is_valid_pricing(pricing)
        self.max_transfer_per_hour = max_transfer_per_hour
        self.resource_loss_per_side = self.pricing.heat_transfer_loss_per_side if isinstance(self.pricing,
                                                                                             HeatingPrice) else 0.0
        
    def _is_valid_pricing(self, pricing: Union[HeatingPrice, ElectricityPrice]):
        if self.resource != pricing.resource:
            raise ValueError("Resource and pricing resource for GridAgent does not match up!")
        return pricing

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None) -> List[GrossBid]:
        # Submit a bid to sell energy
        # Get the retail price, taxes will be added later
        retail_price = self.pricing.get_estimated_retail_price(period, include_tax=False)
        # Sell up to self.max_transfer_per_hour kWh
        bid_to_sell = self.construct_gross_bid(period, Action.SELL, self.resource, self.max_transfer_per_hour,
                                               retail_price)
        # Note: In FED, this agent also submits a BUY bid at "wholesale price". To implement this, we'd need a way
        # for the market solver to know that such a bid doesn't _have to_ be filled. Not sure how this was handled in
        # FED. For us, the "wholesale price" comes into the pricing through the other selling agents: They check what
        # the wholesale price is, and then set that as a lowest-allowed asking price for their sell bids (since if the
        # local price was to be lower than that, those agents would just sell directly to the external grid instead).
        return [bid_to_sell]

    def construct_gross_bid(self, period, action, resource, quantity, price) -> GrossBid:
        return GrossBid(period, action, resource, quantity, price, self.guid, True)

    def make_prognosis(self, period: datetime.datetime, resource: Resource) -> float:
        # FUTURE: Make prognoses of the price, instead of using actual? Although we are already using the day-ahead?
        pass

    def get_actual_usage(self, period: datetime.datetime, resource: Resource) -> float:
        pass

    def make_trades_given_clearing_price(self, local_market_enabled: bool, period: datetime.datetime,
                                         clearing_prices: Dict[Resource, float],
                                         accepted_bids_for_agent: List[NetBidWithAcceptanceStatus]) -> \
            Tuple[List[Trade], Dict[TradeMetadataKey, Any]]:
        # The external grid is used to make up for any differences on the local market. Therefore, these will be
        # calculated at a later stage (in calculate_external_trades)
        return [], {}

    def calculate_external_trades(self, trades_excl_external: Iterable[Trade], clearing_prices: Dict[Resource, float]) \
            -> List[Trade]:
        trades_to_add: List[Trade] = []

        trades_for_this_resource = [trade for trade in trades_excl_external if trade.resource == self.resource]

        if len(trades_for_this_resource) == 0:
            return []

        all_periods = set([trade.period for trade in trades_for_this_resource])
        if len(all_periods) > 1:
            raise RuntimeError("When calculating external trades, received trades for more than 1 trading period!")
        period = all_periods.pop()

        trades_for_period_resource = [trade for trade in trades_for_this_resource if trade.period == period]
        # Using "estimated" price here rather than "exact", so we're gonna have to calculate the difference between
        # them, and who pays that, at a later stage
        retail_price = self.pricing.get_estimated_retail_price(period, include_tax=True)
        wholesale_price = self.pricing.get_estimated_wholesale_price(period)

        self.calculate_external_trades_for_resource_and_market(Market.LOCAL, period, self.resource,
                                                               trades_for_period_resource, trades_to_add,
                                                               retail_price, wholesale_price,
                                                               clearing_prices[self.resource])
        self.calculate_external_trades_for_resource_and_market(Market.EXTERNAL, period, self.resource,
                                                               trades_for_period_resource, trades_to_add,
                                                               retail_price, wholesale_price,
                                                               clearing_prices[self.resource])
        return trades_to_add

    def calculate_external_trades_for_resource_and_market(self, market: Market, period: datetime.datetime,
                                                          resource: Resource, trades_for_this_resource: Iterable[Trade],
                                                          trades_to_add: List[Trade], retail_price: float,
                                                          wholesale_price: float, local_clearing_price: float):
        trades_for_this_resource_and_market = [trade for trade in trades_for_this_resource if trade.market == market]
        sum_buys = sum(
            [trade.quantity_pre_loss for trade in trades_for_this_resource_and_market if trade.action == Action.BUY])
        sum_sells = sum(
            [trade.quantity_post_loss for trade in trades_for_this_resource_and_market if trade.action == Action.SELL])
        if sum_buys > sum_sells:
            deficit_in_market = sum_buys - sum_sells
            need_to_provide = deficit_in_market / (1 - self.resource_loss_per_side)
            tax_to_pay = self.pricing.elec_tax if isinstance(self.pricing, ElectricityPrice) else 0.0
            trades_to_add.append(
                Trade(period=period, action=Action.SELL, resource=resource, quantity=need_to_provide,
                      price=retail_price, source=self.guid, by_external=True, market=market,
                      loss=self.resource_loss_per_side, tax_paid=tax_to_pay))
            if market == Market.LOCAL:
                if local_clearing_price < retail_price:
                    # What happened here is that the market solver believed that locally produced energy would cover
                    # the needs of all agents, but it turned out to not be the case, so we had to import some energy
                    # from the external grid, at a higher price than the local price. Some penalisation will be
                    # applied in the balance manager.
                    logger.debug("In period {}: External grid sells at {:.5f} SEK/kWh to the local market, but the "
                                 "clearing price was {:.5f} SEK/kWh.".
                                 format(period, retail_price, local_clearing_price))
                elif local_clearing_price - retail_price > 1e-10:
                    logger.warning("In period {}: Unexpected result: Local clearing price higher than external retail "
                                   "price".format(period))
        elif sum_buys < sum_sells:
            surplus_in_market = sum_sells - sum_buys
            need_to_buy = surplus_in_market * (1 - self.resource_loss_per_side)
            trades_to_add.append(
                Trade(period=period, action=Action.BUY, resource=resource, quantity=need_to_buy, price=wholesale_price,
                      source=self.guid, by_external=True, market=market,
                      loss=self.resource_loss_per_side))
            if market == Market.LOCAL:
                if local_clearing_price > wholesale_price:
                    # What happened here is that the market solver believed that there would be a local deficit,
                    # but it turned out to not be the case, instead there was a local surplus. So, producing agents
                    # had to export some energy to the external grid, at a lower price than the local price. Some
                    # penalisation will be applied in the balance manager.
                    logger.debug("In period {}: External grid buys at {:.5f} SEK/kWh from the local market, but the "
                                 "clearing price was {:.5f} SEK/kWh".
                                 format(period, wholesale_price, local_clearing_price))
                elif wholesale_price - local_clearing_price > 1e-10:
                    logger.warning("In period {}: Unexpected result: Local clearing price lower than external "
                                   "wholesale price".format(period))
