from unittest import TestCase

import pandas as pd

from tradingplatformpoc import generate_mock_data


class Test(TestCase):

    def test_is_major_holiday_sweden(self):
        xmas_eve = pd.Timestamp('2017-12-24T01', tz='UTC')
        self.assertTrue(generate_mock_data.is_major_holiday_sweden(xmas_eve))
        xmas_eve_in_tz_far_away = pd.Timestamp('2017-12-24T01', tz='Australia/Sydney')
        self.assertFalse(generate_mock_data.is_major_holiday_sweden(xmas_eve_in_tz_far_away))

    def test_is_day_before_major_holiday_sweden(self):
        new_years_eve = pd.Timestamp('2017-12-31T01', tz='UTC')
        self.assertTrue(generate_mock_data.is_day_before_major_holiday_sweden(new_years_eve))
        new_years_eve_in_tz_far_away = pd.Timestamp('2017-12-31T01', tz='Australia/Sydney')
        self.assertFalse(generate_mock_data.is_day_before_major_holiday_sweden(new_years_eve_in_tz_far_away))
