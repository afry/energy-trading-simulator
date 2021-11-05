import math
from unittest import TestCase

from bid import Bid, Action, Resource
from market_solver import MarketSolver


class TestMarketSolver(TestCase):

    ms = MarketSolver()

    def test_resolve_bids_1(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 100, 1),
                Bid(Action.BUY, Resource.ELECTRICITY, 100, 1.5)]
        # Someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 100 kWh at 1.5 SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(1, clearing_price)

    def test_resolve_bids_2(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 100, 1),
                Bid(Action.BUY, Resource.ELECTRICITY, 100, 0.5)]
        # Someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 100 kWh at 0.5 SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(1, clearing_price)

    def test_resolve_bids_3(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 100, 0),
                Bid(Action.SELL, Resource.ELECTRICITY, 100, 1.5),
                Bid(Action.SELL, Resource.ELECTRICITY, 10000, 10),
                Bid(Action.BUY, Resource.ELECTRICITY, 200, math.inf)]
        # Someone willing to sell 100 kWh at 0 SEK/kWh,
        # someone willing to sell 100 kWh at 1.5 SEK/kWh,
        # someone willing to sell 10000 kWh at 10 SEK/kWh,
        # someone willing to buy 200 kWh at Inf SEK/kWh.
        # Clearing price should be 1.5 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(1.5, clearing_price)

    def test_resolve_bids_4(self):
        bids = [Bid(Action.SELL, Resource.ELECTRICITY, 10000, 2),
                Bid(Action.BUY, Resource.ELECTRICITY, 10000, 0.25),
                Bid(Action.SELL, Resource.ELECTRICITY, 100, 0.75),
                Bid(Action.SELL, Resource.ELECTRICITY, 100, 1),
                Bid(Action.BUY, Resource.ELECTRICITY, 200, math.inf)]
        # Top 2 bids being typical for external grid
        # Someone willing to sell 100 kWh at 0.75 SEK/kWh,
        # someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 200 kWh at Inf SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_price = self.ms.resolve_bids(bids)
        self.assertEqual(1, clearing_price)

    def test_resolve_bids_5(self):
        bids = [Bid(Action.BUY, Resource.ELECTRICITY, 10000, 0.25),
                Bid(Action.SELL, Resource.ELECTRICITY, 100, 0.75),
                Bid(Action.BUY, Resource.ELECTRICITY, 200, math.inf)]
        with self.assertRaises(RuntimeError):
            self.ms.resolve_bids(bids)
