import datetime
from unittest import TestCase

import pandas as pd

import polars as pl

from tradingplatformpoc.generate_data.generation_functions.non_residential.commercial import \
    simulate_commercial_area_cooling
from tradingplatformpoc.generate_data.generation_functions.non_residential.school import is_break


class Test(TestCase):

    def test_is_break(self):
        """Simple test of is_break method. Using UTC just because it is the most convenient."""
        self.assertTrue(is_break(datetime.datetime(2019, 7, 1, tzinfo=datetime.timezone.utc)))
        self.assertFalse(is_break(datetime.datetime(2019, 9, 1, tzinfo=datetime.timezone.utc)))

    def test_cooling(self):
        # Set the start date and time
        start_date = datetime.datetime(2019, 1, 1, 0, 0, 0)

        # Set the number of hours for the full year
        num_hours_in_year = 365 * 24

        # Create a list of datetime values with hourly increments
        date_values = [start_date + datetime.timedelta(hours=i) for i in range(num_hours_in_year)]

        input_df = pd.DataFrame({'datetime': date_values})
        cooling = simulate_commercial_area_cooling(1000, 1, pl.from_pandas(input_df).lazy(), 34, 0.2, 8760)
        output_pd_df = cooling.collect().to_pandas()
        self.assertAlmostEqual(34000, output_pd_df['value'].sum())
