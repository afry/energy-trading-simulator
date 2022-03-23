import datetime
import logging
from typing import Dict, Iterable, List, Set, Tuple

import numpy as np

from tradingplatformpoc.bid import Action, Bid, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES

logger = logging.getLogger(__name__)


def resolve_bids(period: datetime.datetime, bids: Iterable[Bid]) -> \
        Tuple[Dict[Resource, float], List[BidWithAcceptanceStatus]]:
    """Function for resolving all bids for the next trading period.
    Will try to find the lowest price where supply equals or exceeds demand.
    @return A dict with clearing prices per energy carrier, and a list of BidWithAcceptanceStatus
    """

    clearing_prices_dict: Dict[Resource, float] = {}
    bids_with_acceptance_status: List[BidWithAcceptanceStatus] = []

    for resource in ALL_IMPLEMENTED_RESOURCES:
        bids_for_resource = [x for x in bids if x.resource == resource]
        bwas_for_resource: List[BidWithAcceptanceStatus] = []
        if not has_at_least_one_bid_each_side(bids_for_resource):
            logger.debug('For period {}, {} had only bids on one side! Setting clearing price to NaN'.
                         format(period, resource))
            clearing_prices_dict[resource] = np.nan
            bwas_for_resource = no_bids_accepted(bids_for_resource)
        else:
            price_points = get_price_points(bids_for_resource)

            demand_which_needs_to_be_filled = 0.0
            for bid in bids_for_resource:
                if bid.action == Action.BUY and bid.price == float("inf"):
                    demand_which_needs_to_be_filled = demand_which_needs_to_be_filled + bid.quantity

            for price_point in sorted(price_points):
                # Going through price points in ascending order
                supply_for_price_point = 0.0
                for bid in bids_for_resource:
                    if bid.action == Action.SELL:
                        if bid.price <= price_point:
                            supply_for_price_point = supply_for_price_point + bid.quantity

                if supply_for_price_point >= demand_which_needs_to_be_filled and supply_for_price_point > 0:
                    # Found an acceptable price!
                    # Now specify what bids were accepted.
                    for bid in bids_for_resource:
                        if bid.action == Action.SELL:
                            if bid.price <= price_point:
                                bwas_for_resource.append(BidWithAcceptanceStatus.from_bid(bid, True))
                            else:
                                bwas_for_resource.append(BidWithAcceptanceStatus.from_bid(bid, False))
                        else:  # BUY
                            if bid.price >= price_point:
                                bwas_for_resource.append(BidWithAcceptanceStatus.from_bid(bid, True))
                            else:
                                bwas_for_resource.append(BidWithAcceptanceStatus.from_bid(bid, False))
                    clearing_prices_dict[resource] = price_point
                    break

            if resource not in clearing_prices_dict:
                # This means we haven't found a clearing price for this resource
                clearing_price, bwas_for_resource = deal_with_no_solution_found(bids_for_resource, period)
                clearing_prices_dict[resource] = clearing_price

            if len(bwas_for_resource) != len(bids_for_resource):
                # Should never happen
                logger.warning('Period {}, Resource {}, market solver lost a bid somewhere!'.format(period, resource))
        bids_with_acceptance_status.extend(bwas_for_resource)

    return clearing_prices_dict, bids_with_acceptance_status


def get_price_points(bids: Iterable[Bid]) -> Set[float]:
    return set([x.price for x in bids])


def deal_with_no_solution_found(bids_without_acceptance_status: Iterable[Bid], period: datetime.datetime) -> \
        Tuple[float, List[BidWithAcceptanceStatus]]:
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


def no_bids_accepted(bids_without_acceptance_status: Iterable[Bid]) -> List[BidWithAcceptanceStatus]:
    return [BidWithAcceptanceStatus.from_bid(bid, False) for bid in bids_without_acceptance_status]


def has_at_least_one_bid_each_side(bids: Iterable[Bid]) -> bool:
    """If this isn't true, the market solver won't need to do any work, essentially."""
    buy_bids = [x for x in bids if x.action == Action.BUY]
    sell_bids = [x for x in bids if x.action == Action.SELL]
    return len(buy_bids) > 0 and len(sell_bids) > 0
