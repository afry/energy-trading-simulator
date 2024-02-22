import datetime
from typing import Any, Dict, Tuple

import numpy as np

import polars as pl

from tradingplatformpoc.generate_data.generation_functions.common import scale_energy_consumption
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


def simulate_commercial_area_total_heating(mock_data_constants: Dict[str, Any], commercial_gross_floor_area_m2: float,
                                           random_seed: int, input_df: pl.LazyFrame, n_rows: int) -> \
        Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas and
    https://doc.afdrift.se/display/RPJ/Coop+heating+energy+use+mock-up
    @return Two pl.LazyFrames with datetimes and hourly heating load, in kWh. The first space heating, the second hot
        tap water.
    """
    space_heating_per_year_m2 = mock_data_constants['CommercialSpaceHeatKwhPerYearM2']
    space_heating = simulate_space_heating(commercial_gross_floor_area_m2, random_seed, input_df,
                                           space_heating_per_year_m2, get_commercial_heating_consumption_hourly_factor,
                                           n_rows)

    hot_tap_water_per_year_m2 = mock_data_constants['CommercialHotTapWaterKwhPerYearM2']
    hot_tap_water_relative_error_std_dev = mock_data_constants['CommercialHotTapWaterRelativeErrorStdDev']
    hot_tap_water = simulate_hot_tap_water(commercial_gross_floor_area_m2, random_seed, input_df,
                                           hot_tap_water_per_year_m2, get_commercial_heating_consumption_hourly_factor,
                                           hot_tap_water_relative_error_std_dev,
                                           n_rows)
    return space_heating, hot_tap_water


def simulate_commercial_area_cooling(commercial_gross_floor_area: float, random_seed: int, input_df: pl.LazyFrame,
                                     kwh_cooling_per_yr_per_m2: float, rel_error_std_dev: float, n_rows: int) \
        -> pl.LazyFrame:
    rng = np.random.default_rng(random_seed)
    lf = input_df.select(
        [pl.col('datetime'), pl.col('datetime').apply(lambda x: get_cooling_consumption_kwh(x)).alias('time_factors')])
    lf = lf.with_column(pl.Series(name='relative_errors',
                                  values=rng.normal(0, rel_error_std_dev, n_rows)))
    lf = lf.with_column(
        (pl.col('time_factors') * (1 + pl.col('relative_errors'))).alias('value')
    )
    return scale_energy_consumption(lf, commercial_gross_floor_area, kwh_cooling_per_yr_per_m2, n_rows)


def get_cooling_consumption_kwh(timestamp: datetime.datetime) -> float:
    """Returns a dimensionless scaling factor for cooling."""
    return (get_cooling_month_scaling_factor(timestamp.month)
            * COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR[timestamp.hour])


def get_cooling_month_scaling_factor(month: int) -> float:
    """Returns a dimensionless scaling factor. Values from BDAB. See https://doc.afdrift.se/x/cgLBAg"""
    if month == 4:
        return 0.142449331673908
    elif month == 5:
        return 2.19526298112194
    elif month == 6:
        return 7.16367834002871
    elif month == 7:
        return 18.4204412705042
    elif month == 8:
        return 16.4748764483724
    elif month == 9:
        return 1.58772770812892
    return 0
