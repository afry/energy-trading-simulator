import math
from unittest import TestCase

from tradingplatformpoc.bid import Action, GrossBid, NetBid, Resource


class TestGrossBid(TestCase):

    def test_create_net_bid(self):
        """Test creation of a NetBid, from a GrossBid with inf price"""
        gross_bid = GrossBid(Action.BUY, Resource.ELECTRICITY, 200, math.inf, 'BuildingAgent', False)
        net_bid = NetBid.from_gross_bid(gross_bid, gross_bid.price + 0.49)
        self.assertAlmostEqual(200, net_bid.quantity)
        self.assertTrue(gross_bid.price == float("inf"))
        self.assertTrue(net_bid.price == float("inf"))

    def test_co2_intensity_validation_sell(self):
        """Test that an exception is thrown if a SELL bid is created with negative co2 intensity"""
        with self.assertRaises(ValueError):
            GrossBid(Action.SELL, Resource.ELECTRICITY, 200, math.inf, 'BuildingAgent', False, -0.1)
    
    def test_co2_intensity_validation_sell_none(self):
        """Test that an exception is thrown if a SELL bid is created with no co2 intensity"""
        with self.assertRaises(ValueError):
            GrossBid(Action.SELL, Resource.ELECTRICITY, 200, math.inf, 'BuildingAgent', False)

    def test_co2_intensity_validation_buy(self):
        """Test that an exception is thrown if a BUY bid is created with a co2_intensity"""
        with self.assertRaises(ValueError):
            GrossBid(Action.BUY, Resource.ELECTRICITY, 200, math.inf, 'BuildingAgent', False, 0.1)
