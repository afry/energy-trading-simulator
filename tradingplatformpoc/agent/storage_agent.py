import datetime
import logging
from typing import List, Union

import numpy as np

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.bid import Action, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.trade import Market
from tradingplatformpoc.trading_platform_utils import minus_n_hours

LOWEST_BID_QUANTITY = 0.001  # Bids with a lower quantity than this won't have any real effect, will only clog things up

logger = logging.getLogger(__name__)


class StorageAgent(IAgent):
    """The agent for a storage actor.

    The storage agent currently works on the logic that it tries to buy when energy is cheap, and sell when it is
    expensive. It will look at the local market clearing prices over the last N hours (call this X), and submit bids
    with a price which is equal to some percentile of X. Similarly, it will submit sell bids with a price equal to
    some (other, higher) percentile of X.
    """
    data_store: DataStore
    digital_twin: StorageDigitalTwin
    go_back_n_hours: int
    if_lower_than_this_percentile_then_buy: int
    if_higher_than_this_percentile_then_sell: int
    # If there isn't {go_back_n_hours} data available, will allow down to {need_at_least_n_hours} hours of data. If
    # there is even less than that available, will throw an error.
    need_at_least_n_hours: int

    def __init__(self, data_store: DataStore, digital_twin: StorageDigitalTwin,
                 n_hours_to_look_back: int, buy_price_percentile: int, sell_price_percentile: int, guid="StorageAgent"):
        super().__init__(guid, data_store)
        self.digital_twin = digital_twin
        self.go_back_n_hours = n_hours_to_look_back
        # Upper and lower thresholds
        if sell_price_percentile < buy_price_percentile:
            logger.warning('In StorageAgent, sell_price_percentile should be higher than buy_price_percentile, but had '
                           'buy_price_percentile={} and sell_price_percentile={}'.format(buy_price_percentile,
                                                                                         sell_price_percentile))
        self.if_lower_than_this_percentile_then_buy = buy_price_percentile
        self.if_higher_than_this_percentile_then_sell = sell_price_percentile
        self.need_at_least_n_hours = int(self.go_back_n_hours / 2)

    def make_bids(self, period: datetime.datetime, clearing_prices_dict: Union[dict, None]):
        bids = []

        if clearing_prices_dict is not None:
            clearing_prices_dict = dict(clearing_prices_dict)
        else:
            logger.warning('No historical clearing prices were provided to StorageAgent! Will use Nordpool spot '
                           'prices instead.')
            clearing_prices_dict = {}

        nordpool_prices_last_n_hours_dict = self.data_store.get_nordpool_prices_last_n_hours_dict(period,
                                                                                                  self.go_back_n_hours)
        prices_last_n_hours = get_prices_last_n_hours(period, self.go_back_n_hours, clearing_prices_dict,
                                                      nordpool_prices_last_n_hours_dict)
        if len(prices_last_n_hours) < self.need_at_least_n_hours:
            raise RuntimeError("StorageAgent '{}' needed at least {} hours of historical prices to function, but was "
                               "only provided with {} hours.".
                               format(self.guid, self.need_at_least_n_hours, len(prices_last_n_hours)))

        buy_quantity = self.calculate_buy_quantity()
        if buy_quantity >= LOWEST_BID_QUANTITY:
            bids.append(self.construct_bid(action=Action.BUY,
                                           quantity=buy_quantity,
                                           price=self.calculate_buy_price(prices_last_n_hours),
                                           resource=Resource.ELECTRICITY))

        sell_quantity = self.calculate_sell_quantity()
        if sell_quantity >= LOWEST_BID_QUANTITY:
            bids.append(self.construct_bid(action=Action.SELL,
                                           quantity=sell_quantity,
                                           price=self.calculate_sell_price(prices_last_n_hours),
                                           resource=Resource.ELECTRICITY))
        return bids

    def make_prognosis(self, period: datetime.datetime):
        pass

    def get_actual_usage(self, period: datetime.datetime):
        pass

    def make_trade_given_clearing_price(self, period: datetime.datetime, clearing_price: float,
                                        clearing_prices_dict: dict,
                                        accepted_bids_for_agent: List[BidWithAcceptanceStatus]):
        # In this implementation, the battery never sells or buys directly from the external grid.
        if len(accepted_bids_for_agent) > 1:
            # As we are currently only supporting one Resource (electricity), this would be unexpected
            raise RuntimeError("More than 1 accepted bid in period {} for storage agent '{}'".format(period, self.guid))
        elif len(accepted_bids_for_agent) == 1:
            bid_quantity = accepted_bids_for_agent[0].quantity
            bid_resource = accepted_bids_for_agent[0].resource
            if accepted_bids_for_agent[0].action == Action.BUY:
                actual_charge_quantity = self.digital_twin.charge(bid_quantity)
                if actual_charge_quantity > 0:
                    return self.construct_trade(Action.BUY, bid_resource, actual_charge_quantity,
                                                clearing_price, Market.LOCAL, period)
            else:  # action was SELL
                actual_discharge_quantity = self.digital_twin.discharge(bid_quantity)
                if actual_discharge_quantity > 0:
                    return self.construct_trade(Action.SELL, bid_resource, actual_discharge_quantity,
                                                clearing_price, Market.LOCAL, period)
        return None

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


def get_prices_last_n_hours(period: datetime.datetime, n_hours: int, clearing_prices_dict: dict,
                            nordpool_prices_last_n_hours_dict: dict) -> List[float]:
    """
    Tries to get the clearing price for the last n hours. If it doesn't exist (i.e. if the market was just started up)
    it will get the Nordpool spot price instead.
    @param period: Current trading period
    @param n_hours: How many hours to go back
    @param clearing_prices_dict: dict with datetime keys, float values
    @param nordpool_prices_last_n_hours_dict: dict with datetime keys, float values
    @return: A list with length at most n_hours with floats. Can be shorter than n_hours if there is no data available
        far enough back.
    """
    prices_last_n_hours = []
    for i in range(n_hours):
        t = minus_n_hours(period, i + 1)
        if t in clearing_prices_dict:
            prices_last_n_hours.append(clearing_prices_dict[t])
        elif t in nordpool_prices_last_n_hours_dict:
            prices_last_n_hours.append(nordpool_prices_last_n_hours_dict[t])
    return prices_last_n_hours
