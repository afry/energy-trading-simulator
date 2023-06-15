import datetime
from unittest import TestCase

from tradingplatformpoc.generate_data.mock_data_generation_functions import is_break


class Test(TestCase):

    def test_is_break(self):
        """Simple test of is_break method. Using UTC just because it is the most convenient."""
        self.assertTrue(is_break(datetime.datetime(2019, 7, 1, tzinfo=datetime.timezone.utc)))
        self.assertFalse(is_break(datetime.datetime(2019, 9, 1, tzinfo=datetime.timezone.utc)))
