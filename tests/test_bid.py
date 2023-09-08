import datetime
import math
from unittest import TestCase

import pytz

from tradingplatformpoc.market.bid import Action, GrossBid, NetBid, Resource


class TestGrossBid(TestCase):

    some_datetime = datetime.datetime(2019, 1, 2, tzinfo=pytz.utc)

    def test_create_net_bid(self):
        """Test creation of a NetBid, from a GrossBid with inf price"""
        gross_bid = GrossBid(self.some_datetime, Action.BUY,
                             Resource.ELECTRICITY, 200, math.inf, 'BuildingAgent', False)
        net_bid = NetBid.from_gross_bid(gross_bid, gross_bid.price + 0.49)
        self.assertAlmostEqual(200, net_bid.quantity)
        self.assertTrue(gross_bid.price == float("inf"))
        self.assertTrue(net_bid.price == float("inf"))
