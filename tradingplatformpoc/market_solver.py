from typing import Iterable, List, Set, Tuple

from tradingplatformpoc.bid import Action, Bid, BidWithAcceptanceStatus


class MarketSolver:
    """An entity that resolves bids towards the market in a way that fulfills the constraints of the bidding entities"""

    def resolve_bids(self, bids: Iterable[Bid]) -> Tuple[float, List[BidWithAcceptanceStatus]]:
        """Function for resolving all bids for the next trading period.
        Will try to find the lowest price where supply equals or exceeds demand.
        @return A clearing price as a float, and a list of BidWithAcceptanceStatus
        """

        price_points = self.get_price_points(bids)
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

        raise NoSolutionFoundError()

    @staticmethod
    def get_price_points(bids: Iterable[Bid]) -> Set[float]:
        return set([x.price for x in bids])


class NoSolutionFoundError(Exception):
    """
    Raised when the market solver cannot find a price point for which the demand is covered by the supply
    """
    pass
