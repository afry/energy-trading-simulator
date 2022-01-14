import datetime
import logging
from typing import Iterable, List, Set, Tuple

import numpy as np

from tradingplatformpoc.bid import Action, Bid, BidWithAcceptanceStatus

logger = logging.getLogger(__name__)


def resolve_bids(period: datetime.datetime, bids: Iterable[Bid]) -> Tuple[float, List[BidWithAcceptanceStatus]]:
    """Function for resolving all bids for the next trading period.
    Will try to find the lowest price where supply equals or exceeds demand.
    @return A clearing price as a float, and a list of BidWithAcceptanceStatus
    """

    price_points = get_price_points(bids)
    bids_with_acceptance_status = []

    for price_point in sorted(price_points):
        # Going through price points in ascending order
        supply_for_price_point = 0.0
        demand_for_price_point = 0.0
        for bid in bids:
            if bid.action == Action.SELL:
                if bid.price <= price_point:
                    supply_for_price_point = supply_for_price_point + bid.quantity
            else:  # BUY
                if bid.price >= price_point:
                    demand_for_price_point = demand_for_price_point + bid.quantity

        if supply_for_price_point >= demand_for_price_point:
            # Found an acceptable price!
            # Now specify what bids were accepted.
            for bid in bids:
                if bid.action == Action.SELL:
                    if bid.price <= price_point:
                        bids_with_acceptance_status.append(BidWithAcceptanceStatus.from_bid(bid, True))
                    else:
                        bids_with_acceptance_status.append(BidWithAcceptanceStatus.from_bid(bid, False))
                else:  # BUY
                    if bid.price >= price_point:
                        bids_with_acceptance_status.append(BidWithAcceptanceStatus.from_bid(bid, True))
                    else:
                        bids_with_acceptance_status.append(BidWithAcceptanceStatus.from_bid(bid, False))
            return price_point, bids_with_acceptance_status

    return deal_with_no_solution_found(bids, period)


def get_price_points(bids: Iterable[Bid]) -> Set[float]:
    return set([x.price for x in bids])


def deal_with_no_solution_found(bids_flat: Iterable[Bid], period: datetime.datetime) -> \
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
    return np.nan, [BidWithAcceptanceStatus.from_bid(bid, False) for bid in bids_flat]
