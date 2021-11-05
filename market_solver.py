from bid import Bid, Action
from typing import List


class MarketSolver:
    """An entity that resolves bids towards the market in a way that fulfills the constraints of the bidding entities"""

    def resolve_bids(self, bids: List[Bid]):
        """Function for resolving all bids for the next trading period"""

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
                return price_point

        raise Exception("No acceptable price found!")

    @staticmethod
    def get_price_points(bids):
        price_points = set()
        for bid in bids:
            price_points.add(bid.price)
        return price_points
