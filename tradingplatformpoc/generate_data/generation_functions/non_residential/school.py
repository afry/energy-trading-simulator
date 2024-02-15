import datetime
from typing import Any, Dict, Tuple

import polars as pl

from tradingplatformpoc.generate_data.generation_functions.non_residential.common import simulate_hot_tap_water, \
    simulate_space_heating


# Constants used in the 'is_break' method. Better to instantiate these here, since is_break is called many times, and
# instantiating these over and over again is really unnecessary.
# Year doesn't really matter, we'll only use the day-of-year
JUST_SOME_NONE_LEAP_YEAR = 2019
# Summer break 15/6 - 15/8
SUMMER_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 6, 15).timetuple().tm_yday
SUMMER_END = SUMMER_START + 60
# Fall break 1/11 - 7/11
FALL_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 11, 1).timetuple().tm_yday
FALL_END = FALL_START + 7
# Christmas break 22/12 - 2/1
CHRISTMAS_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 12, 22).timetuple().tm_yday
CHRISTMAS_END = CHRISTMAS_START + 14
# Sportlov 15/2 - 21/2
SPRING_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 2, 1).timetuple().tm_yday
SPRING_END = SPRING_START + 7
# Easter 07/04 - 14/04
# Easter moves yearly, but since we are only interested in capturing the feature
# of a week off school sometime in mid-spring, we simply chose an average date (April 7th)
EASTER_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 4, 7).timetuple().tm_yday
EASTER_END = EASTER_START + 7


def is_break(timestamp: datetime.datetime):
    # We compare the day-of-year to some pre-defined starts and ends of break periods
    day_of_year = timestamp.timetuple().tm_yday

    # Return true if timestamp falls on break, false if not
    if SUMMER_START <= day_of_year <= SUMMER_END:
        return True

    if FALL_START <= day_of_year <= FALL_END:
        return True

    if CHRISTMAS_START <= day_of_year <= CHRISTMAS_END:
        return True

    if SPRING_START <= day_of_year <= SPRING_END:
        return True

    if EASTER_START <= day_of_year <= EASTER_END:
        return True


def get_school_heating_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    """Assuming opening hours 8-17:00 except for weekends and breaks"""
    if timestamp.weekday() == 5 or timestamp.weekday() == 6:  # Saturday or sunday
        return 0.5
    if is_break(timestamp):
        return 0.5
    if not (8 <= timestamp.hour < 17):
        return 0.5
    return 1


def simulate_school_area_heating(mock_data_constants: Dict[str, Any], school_gross_floor_area_m2: float,
                                 random_seed: int, input_df: pl.LazyFrame, n_rows: int
                                 ) -> Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    This function follows the recipe outlined in the corresponding function for commercial buildings.
    @return Two pl.DataFrames with datetimes and hourly total heating load, in kWh.
    """
    space_heating_per_year_m2 = mock_data_constants['SchoolSpaceHeatKwhPerYearM2']
    space_heating = simulate_space_heating(school_gross_floor_area_m2, random_seed, input_df,
                                           space_heating_per_year_m2,
                                           get_school_heating_consumption_hourly_factor, n_rows)
    hot_tap_water_per_year_m2 = mock_data_constants['SchoolHotTapWaterKwhPerYearM2']
    hot_tap_water_relative_error_std_dev = mock_data_constants['SchoolHotTapWaterRelativeErrorStdDev']
    hot_tap_water = simulate_hot_tap_water(school_gross_floor_area_m2, random_seed, input_df,
                                           hot_tap_water_per_year_m2,
                                           get_school_heating_consumption_hourly_factor,
                                           hot_tap_water_relative_error_std_dev,
                                           n_rows)
    return space_heating, hot_tap_water
