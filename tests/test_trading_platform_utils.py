from collections import Counter
from datetime import datetime
from unittest import TestCase

from tradingplatformpoc.trading_platform_utils import add_all_to_nested_dict, flatten_collection, get_if_exists_else, \
    get_intersection, minus_n_hours


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

    def test_get_if_exists_else(self):
        """
        Test that get_if_exists_else behaves as expected.
        """
        fake_agent = {'PVEfficiency': 0.18}
        default_value = 0.165
        self.assertEqual(0.18, get_if_exists_else(fake_agent, 'PVEfficiency', default_value))
        empty_agent = {}
        self.assertEqual(default_value, get_if_exists_else(empty_agent, 'PVEfficiency', default_value))

    def test_add_all_to_nested_dict(self):
        """Test the add_all_to_nested_dict function."""
        dict1 = {'a': {'c': 0, 'd': 1}, 'b': {'c': 2, 'd': 3}}
        dict2 = {'b': {'e': 4, 'f': 5}, 'g': {'c': 2, 'd': 3}, 'a': {'c': -1}}

        add_all_to_nested_dict(dict1, dict2)

        # Ensure that the sub-dict is added to:
        self.assertEqual(4, len(dict1['b']))
        # Ensure that values from the second input are used:
        self.assertEqual(-1, dict1['a']['c'])
