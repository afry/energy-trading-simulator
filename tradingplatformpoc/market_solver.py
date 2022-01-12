from tradingplatformpoc.bid import Bid, Action
from typing import Iterable


class MarketSolver:
    """An entity that resolves bids towards the market in a way that fulfills the constraints of the bidding entities"""

    def resolve_bids(self, bids: Iterable[Bid]):
        """Function for resolving all bids for the next trading period.
        Will try to find the lowest price where supply equals or exceeds demand."""

        price_points = self.get_price_points(bids)

        for price_point in sorted(price_points):
            # Going through price points in ascending order
            supply_for_price_point = 0
            demand_for_price_point = 0
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
                            bid.set_was_accepted(True)
                        else:
                            bid.set_was_accepted(False)
                    else:  # BUY
                        if bid.price >= price_point:
                            bid.set_was_accepted(True)
                        else:
                            bid.set_was_accepted(False)
                return price_point, bids

        raise RuntimeError("No acceptable price found!")

    @staticmethod
    def get_price_points(bids: Iterable[Bid]):
        return set([x.price for x in bids])
