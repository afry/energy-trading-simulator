import math
from unittest import TestCase

from tradingplatformpoc.bid import Bid, Action, Resource
from tradingplatformpoc.market_solver import MarketSolver


class TestMarketSolver(TestCase):

    ms = MarketSolver()

    def test_resolve_bids_1(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 100, 1, "Seller1"),
                Bid(Action.BUY, Resource.ELECTRICITY, 100, 1.5, "Buyer1")]
        # Someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 100 kWh at 1.5 SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(1, clearing_price)

    def test_resolve_bids_2(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 100, 1, "Seller1"),
                Bid(Action.BUY, Resource.ELECTRICITY, 100, 0.5, "Buyer1")]
        # Someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 100 kWh at 0.5 SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(1, clearing_price)

    def test_resolve_bids_3(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 100, 0, "Seller1"),
                Bid(Action.SELL, Resource.ELECTRICITY, 100, 1.5, "Seller2"),
                Bid(Action.SELL, Resource.ELECTRICITY, 10000, 10, "Grid"),
                Bid(Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1")]
        # Someone willing to sell 100 kWh at 0 SEK/kWh,
        # someone willing to sell 100 kWh at 1.5 SEK/kWh,
        # someone willing to sell 10000 kWh at 10 SEK/kWh,
        # someone willing to buy 200 kWh at Inf SEK/kWh.
        # Clearing price should be 1.5 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(1.5, clearing_price)

    def test_resolve_bids_4(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 10000, 2, "Grid"),
                Bid(Action.SELL, Resource.ELECTRICITY, 100, 0.75, "Seller1"),
                Bid(Action.SELL, Resource.ELECTRICITY, 100, 1, "Seller2"),
                Bid(Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1")]
        # Top 2 bids being typical for external grid
        # Someone willing to sell 100 kWh at 0.75 SEK/kWh,
        # someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 200 kWh at Inf SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(1, clearing_price)

    def test_resolve_bids_5(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 100, 0.75, "Seller1"),
                Bid(Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1")]
        with self.assertRaises(RuntimeError):
            self.ms.resolve_bids(bids)

    def test_resolve_bids_with_local_surplus(self):
        bids = [Bid(Action.BUY, Resource.ELECTRICITY, 192.76354849517332, math.inf, 'BuildingAgent'),
                Bid(Action.SELL, Resource.ELECTRICITY, 100, 0.46069, 'BatteryStorageAgent'),
                Bid(Action.SELL, Resource.ELECTRICITY, 275.3113968, 0.46069, 'PVAgent'),
                Bid(Action.BUY, Resource.ELECTRICITY, 100.8875027389364, math.inf, 'GroceryStoreAgent'),
                Bid(Action.SELL, Resource.ELECTRICITY, 10000, 0.89069, 'ElectricityGridAgent')]
        # Local surplus
        # Clearing price should be 0.46069 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(0.46069, clearing_price)
        # Market solver tries to fulfill the electricity grid's buy bid!
