import datetime
import logging
from typing import Any, Dict, List, Tuple, Union

import numpy as np

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.digitaltwin.battery import Battery
from tradingplatformpoc.market.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Market, Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice

LOWEST_BID_QUANTITY = 0.001  # Bids with a lower quantity than this won't have any real effect, will only clog things up

logger = logging.getLogger(__name__)


class BatteryAgent(IAgent):
    """The agent for a storage actor. Can only store energy of one 'type', i.e. Resource.

    The storage agent currently works on the logic that it tries to buy when energy is cheap, and sell when it is
    expensive. It will look at the local market clearing prices over the last N hours (call this X), and submit bids
    with a price which is equal to some percentile of X. Similarly, it will submit sell bids with a price equal to
    some (other, higher) percentile of X.
    """
    electricity_pricing: ElectricityPrice
    digital_twin: Battery
    resource: Resource = Resource.ELECTRICITY
    go_forward_n_hours: int
    if_lower_than_this_percentile_then_buy: int
    if_higher_than_this_percentile_then_sell: int
    # If there isn't {go_forward_n_hours} data available, will allow down to {need_at_least_n_hours} hours of data. If
    # there is even less than that available, will do nothing.
    need_at_least_n_hours: int

    def __init__(self, electricity_pricing: ElectricityPrice,
                 digital_twin: Battery, n_hours_to_look_forward: int,
                 buy_price_percentile: int, sell_price_percentile: int, guid="BatteryAgent"):
        super().__init__(guid)
        self.electricity_pricing = electricity_pricing
        self.digital_twin = digital_twin
        self.go_forward_n_hours = n_hours_to_look_forward
        # Upper and lower thresholds
        if sell_price_percentile < buy_price_percentile:
            logger.warning('In BatteryAgent, sell_price_percentile should be higher than buy_price_percentile, but had '
                           'buy_price_percentile={} and sell_price_percentile={}'.format(buy_price_percentile,
                                                                                         sell_price_percentile))
        self.if_lower_than_this_percentile_then_buy = buy_price_percentile
        self.if_higher_than_this_percentile_then_sell = sell_price_percentile
        self.need_at_least_n_hours = int(self.go_forward_n_hours / 2)

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None]) -> List[GrossBid]:
        bids: List[GrossBid] = []

        prices_comming_n_hours = self.electricity_pricing.get_nordpool_prices_comming_n_hours_dict(period, 12)

        if period not in prices_comming_n_hours.keys():
            raise RuntimeError("Period {} not available in nordpool data.".format(period))
   
        if len(prices_comming_n_hours.values()) < self.need_at_least_n_hours:
            logger.warning("BatteryAgent '{}' needed at least {} hours of prices to function, but was "
                           "only provided with {} hours.".
                           format(self.guid, self.need_at_least_n_hours, len(prices_comming_n_hours)))
            return bids

        buy_quantity = self.calculate_buy_quantity()
        if buy_quantity >= LOWEST_BID_QUANTITY:
            bids.append(self.construct_elec_bid(period=period,
                                                action=Action.BUY,
                                                quantity=buy_quantity,
                                                price=self.calculate_buy_price(
                                                    list(prices_comming_n_hours.values()))))

        sell_quantity = self.calculate_sell_quantity()
        if sell_quantity >= LOWEST_BID_QUANTITY:
            bids.append(self.construct_elec_bid(period=period,
                                                action=Action.SELL,
                                                quantity=sell_quantity,
                                                price=self.calculate_sell_price(
                                                    list(prices_comming_n_hours.values()))))
        return bids

    def get_clearing_prices_for_resource(self, clearing_prices_hist: Dict[datetime.datetime, Dict[Resource, float]]) \
            -> Dict[datetime.datetime, float]:
        return {k: v[self.resource] for k, v in clearing_prices_hist.items()}

    def make_prognosis(self, period: datetime.datetime, resource: Resource) -> float:
        pass

    def get_actual_usage(self, period: datetime.datetime, resource: Resource) -> float:
        pass

    def make_trades_given_clearing_price(self, period: datetime.datetime, clearing_prices: Dict[Resource, float],
                                         accepted_bids_for_agent: List[NetBidWithAcceptanceStatus]) -> \
            Tuple[List[Trade], Dict[TradeMetadataKey, Any]]:
        trades = []
        # In this implementation, the battery never sells or buys directly from the external grid.
        if len(accepted_bids_for_agent) > 1:
            # Only supporting one Resource, this would be unexpected
            raise RuntimeError("More than 1 accepted bid in period {} for storage agent '{}'".format(period, self.guid))
        elif len(accepted_bids_for_agent) == 1:
            accepted_quantity = accepted_bids_for_agent[0].accepted_quantity
            clearing_price = clearing_prices[self.resource]
            if accepted_bids_for_agent[0].action == Action.BUY:
                actual_charge_quantity = self.digital_twin.charge(accepted_quantity)
                if actual_charge_quantity > 0:
                    trades = [self.construct_elec_trade(period=period, action=Action.BUY,
                                                        quantity=actual_charge_quantity,
                                                        price=clearing_price, market=Market.LOCAL)]
            else:  # action was SELL
                actual_discharge_quantity = self.digital_twin.discharge(accepted_quantity)
                if actual_discharge_quantity > 0:

                    trades = [self.construct_elec_trade(period=period, action=Action.SELL,
                                                        quantity=actual_discharge_quantity, price=clearing_price,
                                                        market=Market.LOCAL,
                                                        tax_paid=self.electricity_pricing.elec_tax_internal,
                                                        grid_fee_paid=self.electricity_pricing.elec_grid_fee_internal)]
        return trades, {TradeMetadataKey.STORAGE_LEVEL: self.digital_twin.capacity_kwh}

    def calculate_buy_price(self, prices_last_n_hours: List[float]):
        buy_price = np.percentile(prices_last_n_hours, self.if_lower_than_this_percentile_then_buy)
        return self.electricity_pricing.get_electricity_net_internal_price_from_nordpool_price(buy_price)

    def calculate_sell_price(self, prices_last_n_hours: List[float]):
        sell_price = np.percentile(prices_last_n_hours, self.if_higher_than_this_percentile_then_sell)
        return self.electricity_pricing.get_electricity_wholesale_price_from_nordpool_price(sell_price)

    def calculate_buy_quantity(self):
        """Will buy 50% of remaining empty space, but not more than the digital twin's charge limit"""
        empty_capacity_kwh = self.digital_twin.max_capacity_kwh - self.digital_twin.capacity_kwh
        return min([empty_capacity_kwh / 2.0, self.digital_twin.charge_limit_kwh])

    def calculate_sell_quantity(self):
        """Will sell 50% of current charge level, but not more than the digital twin's discharge limit"""
        return min([self.digital_twin.capacity_kwh / 2.0, self.digital_twin.discharge_limit_kwh])
