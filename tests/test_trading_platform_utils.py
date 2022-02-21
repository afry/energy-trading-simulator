from collections import Counter
from datetime import datetime
from unittest import TestCase

from tradingplatformpoc.trading_platform_utils import add_numeric_dicts, flatten_collection, get_intersection, \
    minus_n_hours


class Test(TestCase):
    def test_minus_n_hours(self):
        """Test that removing an hour from a datetime, returns a datetime which is one hour earlier."""
        t2 = minus_n_hours(datetime(2021, 12, 10, 11, 0, 0), 1)
        self.assertEqual(datetime(2021, 12, 10, 10, 0, 0), t2)

    def test_get_intersection_of_lists(self):
        """Test that get_intersection works for two lists."""
        list1 = [1, 2, 3]
        list2 = [4, 3, 2]
        self.assertEqual([2, 3], get_intersection(list1, list2))

    def test_get_intersection_of_set_and_list(self):
        """Test that get_intersection works for one set and one list."""
        set1 = {1, 2, 3}
        list2 = [4, 3, 2]
        self.assertEqual([2, 3], get_intersection(set1, list2))

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

    def test_flatten_list_of_lists(self):
        """Test that flatten_collection works as intended for a list of lists"""
        list_of_lists = [[1, 2], [3, 4]]
        self.assertEqual(4, len(flatten_collection(list_of_lists)))

    def test_flatten_list_of_counters(self):
        """Test that flatten_collection works as intended for a list of Counters"""
        c1 = Counter({'red': 4, 'blue': 2})
        c2 = Counter(cats=4, dogs=8)
        list_of_counters = [c1, c2]
        self.assertEqual(4, len(flatten_collection(list_of_counters)))
