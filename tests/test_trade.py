import datetime
from unittest import TestCase

from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.trade import Market, Trade

SOME_DATETIME = datetime.datetime(2019, 1, 2)


class TestTrade(TestCase):

    def test_initialize_with_negative_quantity(self):
        """Test that an error is raised when a Trade is created with a negative quantity."""
        with self.assertRaises(RuntimeError):
            Trade(Action.SELL, Resource.ELECTRICITY, -12.345, 1.0, 'SomeAgent', False, Market.LOCAL, SOME_DATETIME)
