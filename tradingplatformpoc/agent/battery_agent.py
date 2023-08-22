import datetime
import logging
from typing import Any, Dict, List, Tuple, Union

import numpy as np

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.digitaltwin.battery import Battery
from tradingplatformpoc.market.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Market, Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.trading_platform_utils import minus_n_hours

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
    go_back_n_hours: int
    if_lower_than_this_percentile_then_buy: int
    if_higher_than_this_percentile_then_sell: int
    # If there isn't {go_back_n_hours} data available, will allow down to {need_at_least_n_hours} hours of data. If
    # there is even less than that available, will throw an error.
    need_at_least_n_hours: int

    def __init__(self, electricity_pricing: ElectricityPrice,
                 digital_twin: Battery, n_hours_to_look_back: int,
                 buy_price_percentile: int, sell_price_percentile: int, guid="BatteryAgent"):
        super().__init__(guid)
        self.electricity_pricing = electricity_pricing
        self.digital_twin = digital_twin
        self.go_back_n_hours = n_hours_to_look_back
        # Upper and lower thresholds
        if sell_price_percentile < buy_price_percentile:
            logger.warning('In BatteryAgent, sell_price_percentile should be higher than buy_price_percentile, but had '
                           'buy_price_percentile={} and sell_price_percentile={}'.format(buy_price_percentile,
                                                                                         sell_price_percentile))
        self.if_lower_than_this_percentile_then_buy = buy_price_percentile
        self.if_higher_than_this_percentile_then_sell = sell_price_percentile
        self.need_at_least_n_hours = int(self.go_back_n_hours / 2)

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None]) -> List[GrossBid]:
        bids = []

        if clearing_prices_historical is not None:
            clearing_prices_for_resource = self.get_clearing_prices_for_resource(dict(clearing_prices_historical))
        else:
            logger.warning('No historical clearing prices were provided to BatteryAgent! Will use Nordpool spot '
                           'prices instead.')
            clearing_prices_for_resource = {}

        # TODO: Only works for electricity!
        nordpool_prices_last_n_hours_dict = self.electricity_pricing.get_nordpool_prices_last_n_hours_dict(
            period, self.go_back_n_hours)
        prices_last_n_hours = get_prices_last_n_hours(period, self.go_back_n_hours, clearing_prices_for_resource,
                                                      nordpool_prices_last_n_hours_dict)
        if len(prices_last_n_hours) < self.need_at_least_n_hours:
            raise RuntimeError("BatteryAgent '{}' needed at least {} hours of historical prices to function, but was "
                               "only provided with {} hours.".
                               format(self.guid, self.need_at_least_n_hours, len(prices_last_n_hours)))

        buy_quantity = self.calculate_buy_quantity()
        if buy_quantity >= LOWEST_BID_QUANTITY:
            bids.append(self.construct_elec_bid(period=period,
                                                action=Action.BUY,
                                                quantity=buy_quantity,
                                                price=self.calculate_buy_price(prices_last_n_hours)))

        sell_quantity = self.calculate_sell_quantity()
        if sell_quantity >= LOWEST_BID_QUANTITY:
            bids.append(self.construct_elec_bid(period=period,
                                                action=Action.SELL,
                                                quantity=sell_quantity,
                                                price=self.calculate_sell_price(prices_last_n_hours)))
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
                    trades = [self.construct_elec_trade(Action.BUY, actual_charge_quantity,
                                                        clearing_price, Market.LOCAL, period)]
            else:  # action was SELL
                actual_discharge_quantity = self.digital_twin.discharge(accepted_quantity)
                if actual_discharge_quantity > 0:
                    trades = [self.construct_elec_trade(Action.SELL, actual_discharge_quantity,
                                                        clearing_price, Market.LOCAL, period,
                                                        tax_paid=self.electricity_pricing.elec_tax_internal,
                                                        grid_fee_paid=self.electricity_pricing.elec_grid_fee_internal)]
        return trades, {TradeMetadataKey.STORAGE_LEVEL: self.digital_twin.capacity_kwh}

    def calculate_buy_price(self, prices_last_n_hours: List[float]):
        return np.percentile(prices_last_n_hours, self.if_lower_than_this_percentile_then_buy)

    def calculate_sell_price(self, prices_last_n_hours: List[float]):
        return np.percentile(prices_last_n_hours, self.if_higher_than_this_percentile_then_sell)

    def calculate_buy_quantity(self):
        """Will buy 50% of remaining empty space, but not more than the digital twin's charge limit"""
        empty_capacity_kwh = self.digital_twin.max_capacity_kwh - self.digital_twin.capacity_kwh
        return min([empty_capacity_kwh / 2.0, self.digital_twin.charge_limit_kwh])

    def calculate_sell_quantity(self):
        """Will sell 50% of current charge level, but not more than the digital twin's discharge limit"""
        return min([self.digital_twin.capacity_kwh / 2.0, self.digital_twin.discharge_limit_kwh])


def get_prices_last_n_hours(period: datetime.datetime, n_hours: int, clearing_prices_historical: dict,
                            external_prices_last_n_hours_dict: dict) -> List[float]:
    """
    Tries to get the clearing price for the last n hours. If it doesn't exist (i.e. if the market was just started up)
    it will get the Nordpool spot price instead.
    @param period: Current trading period
    @param n_hours: How many hours to go back
    @param clearing_prices_historical: dict with datetime keys, float values
    @param external_prices_last_n_hours_dict: dict with datetime keys, float values
    @return: A list with length at most n_hours with floats. Can be shorter than n_hours if there is no data available
        far enough back.
    """
    ts = [minus_n_hours(period, i + 1) for i in range(n_hours)]
    prices_last_n_hours = [clearing_prices_historical[t] if t in clearing_prices_historical
                           else external_prices_last_n_hours_dict[t] if t in external_prices_last_n_hours_dict
                           else None for t in ts]
    if None in prices_last_n_hours:
        logger.info('Missing prices in last {} hours.'.format(n_hours))
        return [price for price in prices_last_n_hours if price is not None]
    return prices_last_n_hours
