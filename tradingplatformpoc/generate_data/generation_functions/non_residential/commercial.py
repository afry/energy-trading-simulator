import datetime
from typing import Any, Dict, Tuple

import polars as pl

from tradingplatformpoc.generate_data.generation_functions.non_residential.common import simulate_hot_tap_water, \
    simulate_space_heating


COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR = {
    0: 0.2,
    1: 0.2,
    2: 0.2,
    3: 0.2,
    4: 0.2,
    5: 0.2,
    6: 0.3,
    7: 0.5,
    8: 0.7,
    9: 0.91,
    10: 0.92,
    11: 0.93,
    12: 0.94,
    13: 0.95,
    14: 0.96,
    15: 0.97,
    16: 0.98,
    17: 0.99,
    18: 1.0,
    19: 0.6,
    20: 0.2,
    21: 0.2,
    22: 0.2,
    23: 0.2
}


def get_commercial_electricity_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    return COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR[timestamp.hour]


def get_commercial_heating_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    """Assuming opening hours 9-20, roughly similar to COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR"""
    if 9 <= timestamp.hour < 20:
        return 1.0
    else:
        return 0.5


def simulate_commercial_area_total_heating(config_data: Dict[str, Any], commercial_gross_floor_area_m2: float,
                                           random_seed: int, input_df: pl.LazyFrame, n_rows: int) -> \
        Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas and
    https://doc.afdrift.se/display/RPJ/Coop+heating+energy+use+mock-up
    @return Two pl.LazyFrames with datetimes and hourly heating load, in kWh. The first space heating, the second hot
        tap water.
    """
    space_heating_per_year_m2 = config_data['MockDataConstants']['CommercialSpaceHeatKwhPerYearM2']
    space_heating = simulate_space_heating(commercial_gross_floor_area_m2, random_seed, input_df,
                                           space_heating_per_year_m2, get_commercial_heating_consumption_hourly_factor,
                                           n_rows)

    hot_tap_water_per_year_m2 = config_data['MockDataConstants']['CommercialHotTapWaterKwhPerYearM2']
    hot_tap_water_relative_error_std_dev = config_data['MockDataConstants']['CommercialHotTapWaterRelativeErrorStdDev']
    hot_tap_water = simulate_hot_tap_water(commercial_gross_floor_area_m2, random_seed, input_df,
                                           hot_tap_water_per_year_m2, get_commercial_heating_consumption_hourly_factor,
                                           hot_tap_water_relative_error_std_dev,
                                           n_rows)
    return space_heating, hot_tap_water
