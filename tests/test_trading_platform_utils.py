from datetime import datetime
from unittest import TestCase

from tradingplatformpoc.trading_platform_utils import minus_n_hours


class Test(TestCase):
    def test_minus_n_hours(self):
        t2 = minus_n_hours(datetime(2021, 12, 10, 11, 0, 0), 1)
        self.assertEqual(datetime(2021, 12, 10, 10, 0, 0), t2)
