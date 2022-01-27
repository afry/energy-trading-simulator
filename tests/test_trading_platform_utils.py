from datetime import datetime
from unittest import TestCase

from tradingplatformpoc.trading_platform_utils import add_numeric_dicts, minus_n_hours


class Test(TestCase):
    def test_minus_n_hours(self):
        t2 = minus_n_hours(datetime(2021, 12, 10, 11, 0, 0), 1)
        self.assertEqual(datetime(2021, 12, 10, 10, 0, 0), t2)

    def test_add_numeric_dicts(self):
        """Test that add_numeric_dicts works as intended: Add values for keys that exist in both, keep all keys."""
        dict1 = {'a': 9, 'b': 8, 'e': 2}
        dict2 = {'c': 4, 'd': 6, 'e': 2, 'f': 0}
        dict3 = add_numeric_dicts(dict1, dict2)
        self.assertEqual(9, dict3['a'])
        self.assertEqual(8, dict3['b'])
        self.assertEqual(4, dict3['c'])
        self.assertEqual(6, dict3['d'])
        self.assertEqual(4, dict3['e'])
        self.assertEqual(0, dict3['f'])
