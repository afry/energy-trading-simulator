import datetime
import logging
from typing import Dict, Iterable, List, Set, Tuple, Union

import numpy as np

from tradingplatformpoc.bid import Action, NetBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES

logger = logging.getLogger(__name__)


def resolve_bids(period: datetime.datetime, bids: Iterable[NetBid]) -> \
        Tuple[Dict[Resource, float], List[NetBidWithAcceptanceStatus]]:
    """Function for resolving all bids for the next trading period.
    Will try to find the lowest price where supply equals or exceeds demand.
    @return A dict with clearing prices per energy carrier, and a list of BidWithAcceptanceStatus
    """

    clearing_prices_dict: Dict[Resource, float] = {}
    bids_with_acceptance_status: List[NetBidWithAcceptanceStatus] = []

    for resource in ALL_IMPLEMENTED_RESOURCES:
        bids_for_resource = [x for x in bids if x.resource == resource]
        buy_bids_resource = [x for x in bids_for_resource if x.action == Action.BUY]
        sell_bids_resource = [x for x in bids_for_resource if x.action == Action.SELL]
        if not has_at_least_one_bid_each_side(buy_bids_resource, sell_bids_resource):
            logger.debug('For period {}, {} had only bids on one side! Setting clearing price to NaN'.
                         format(period, resource))
            clearing_prices_dict[resource] = np.nan
            bwas_for_resource = no_bids_accepted(bids_for_resource)
        else:
            price_points = get_price_points(bids_for_resource)

            demand_which_needs_to_be_filled = 0.0
            for bid in buy_bids_resource:
                if bid.price == float("inf"):
                    demand_which_needs_to_be_filled = demand_which_needs_to_be_filled + bid.quantity

            clearing_price, supply_for_price_point = calculate_clearing_price(demand_which_needs_to_be_filled,
                                                                              price_points, sell_bids_resource)

            if clearing_price is None:
                # This means we haven't found a clearing price for this resource
                clearing_price, bwas_for_resource = deal_with_no_solution_found(bids_for_resource, period)
            else:
                bwas_for_resource = calculate_bids_with_acceptance_status(clearing_price, buy_bids_resource,
                                                                          sell_bids_resource, supply_for_price_point)
            clearing_prices_dict[resource] = clearing_price

            if len(bwas_for_resource) != len(bids_for_resource):
                # Should never happen
                logger.warning('Period {}, Resource {}, market solver lost a bid somewhere!'.format(period, resource))
        bids_with_acceptance_status.extend(bwas_for_resource)

    return clearing_prices_dict, bids_with_acceptance_status


def calculate_bids_with_acceptance_status(clearing_price: float, buy_bids: List[NetBid],
                                          sell_bids: List[NetBid], supply_for_price_point: float) -> \
        List[NetBidWithAcceptanceStatus]:
    """
    Builds a list of bids with the extra information of how much of their quantity was "accepted" in the market solver.
    """
    bwas_for_resource: List[NetBidWithAcceptanceStatus] = []

    # First, go through buy bids, biggest price first
    buy_quantity_accepted = 0.0
    buy_bid_price_points = get_price_points(buy_bids)
    for buy_bid_price_point in sorted(buy_bid_price_points, reverse=True):
        buy_bids_with_this_price = [bid for bid in buy_bids if bid.price == buy_bid_price_point]
        if buy_bid_price_point < clearing_price:
            for bid in buy_bids_with_this_price:
                bwas_for_resource.append(NetBidWithAcceptanceStatus.from_bid(bid, 0.0))
        else:
            # Accept as much as possible
            total_quantity_at_price_point = sum([bid.quantity for bid in buy_bids_with_this_price])
            max_possible_accept_quantity = supply_for_price_point - buy_quantity_accepted
            frac_to_accept = min(1.0, max_possible_accept_quantity / total_quantity_at_price_point)
            for bid in buy_bids_with_this_price:
                bwas_for_resource.append(NetBidWithAcceptanceStatus.from_bid(bid, bid.quantity * frac_to_accept))
            buy_quantity_accepted = buy_quantity_accepted + total_quantity_at_price_point * frac_to_accept

    # Now go through sell bids, lowest price first
    sell_quantity_accepted = 0.0
    sell_bid_price_points = get_price_points(sell_bids)
    for sell_bid_price_point in sorted(sell_bid_price_points, reverse=False):
        sell_bids_with_this_price = [bid for bid in sell_bids if bid.price == sell_bid_price_point]
        if sell_bid_price_point > clearing_price:
            for bid in sell_bids_with_this_price:
                bwas_for_resource.append(NetBidWithAcceptanceStatus.from_bid(bid, 0.0))
        else:
            # Accept as much as possible
            total_quantity_at_price_point = sum([bid.quantity for bid in sell_bids_with_this_price])
            max_possible_accept_quantity = buy_quantity_accepted - sell_quantity_accepted
            frac_to_accept = min(1.0, max_possible_accept_quantity / total_quantity_at_price_point)
            for bid in sell_bids_with_this_price:
                bwas_for_resource.append(NetBidWithAcceptanceStatus.from_bid(bid, bid.quantity * frac_to_accept))
            sell_quantity_accepted = sell_quantity_accepted + total_quantity_at_price_point * frac_to_accept

    if abs(buy_quantity_accepted - sell_quantity_accepted) > 1e-5:
        logger.warning('buy_quantity_accepted was not equal to sell_quantity_accepted! Difference: '
                       + str(abs(buy_quantity_accepted - sell_quantity_accepted)))
    return bwas_for_resource


def calculate_clearing_price(demand_which_needs_to_be_filled: float, price_points: Set[float],
                             sell_bids_resource: List[NetBid]) -> Tuple[Union[float, None], float]:
    """
    Goes through price points in ascending order. When a price point for which the available supply exceeds or equals
    the demand which "needs to" be filled is found, that price point is returned.
    @return: A tuple, the first entry being the calculated clearing price, and the second being the total supply for
        that price point.
    """
    for price_point in sorted(price_points):
        # Going through price points in ascending order
        supply_for_price_point = 0.0
        for bid in sell_bids_resource:
            if bid.price <= price_point:
                supply_for_price_point = supply_for_price_point + bid.quantity

        if supply_for_price_point >= demand_which_needs_to_be_filled and supply_for_price_point > 0:
            # Found an acceptable price!
            return price_point, supply_for_price_point
    return None, 0


def get_price_points(bids: Iterable[NetBid]) -> Set[float]:
    return set([x.price for x in bids])


def deal_with_no_solution_found(bids_without_acceptance_status: Iterable[NetBid], period: datetime.datetime) -> \
        Tuple[float, List[NetBidWithAcceptanceStatus]]:
    """
    Not entirely clear what we should do here. This will only happen if ExternalGridAgent cannot provide
    enough energy, basically, which should never be the case. Currently, we will set clearing price to np.nan
    and all agents will ignore the local market, and buy/sell directly from/to the external grid instead.
    This is the easiest way of handling it, even though there may be some locally produced electricity which
    could be sold locally, saving money for that seller...
    """
    logger.warning("Market solver found no price for which demand was covered by supply, for period {}".
                   format(period))
    return np.nan, no_bids_accepted(bids_without_acceptance_status)


def no_bids_accepted(bids_without_acceptance_status: Iterable[NetBid]) -> List[NetBidWithAcceptanceStatus]:
    return [NetBidWithAcceptanceStatus.from_bid(bid, 0.0) for bid in bids_without_acceptance_status]


def has_at_least_one_bid_each_side(buy_bids: List[NetBid], sell_bids: List[NetBid]) -> bool:
    """If this isn't true, the market solver won't need to do any work, essentially."""
    return len(buy_bids) > 0 and len(sell_bids) > 0
