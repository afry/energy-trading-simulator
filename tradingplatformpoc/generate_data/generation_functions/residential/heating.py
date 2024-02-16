from typing import Any, Dict, Tuple

import numpy as np

import polars as pl

from tradingplatformpoc.generate_data.generation_functions.common import constants, scale_energy_consumption
from tradingplatformpoc.trading_platform_utils import nan_helper

EVERY_X_HOURS = 3  # Random noise will be piecewise linear, with knots every X hours


def simulate_residential_total_heating(mock_data_constants: Dict[str, Any], df_inputs: pl.LazyFrame, n_rows: int,
                                       gross_floor_area_m2: float, random_seed: int) -> \
        Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    Following along with https://doc.afdrift.se/display/RPJ/Jonstaka+heating+mock-up
    But as for electricity, we'll just see the whole sub-area as 1 house, shouldn't matter too much.
    df_inputs needs to contain 'rad_energy' and 'hw_energy' columns, with the Vetelangden data.
    Returns two pl.LazyFrames with datetimes and simulated data: The first representing space heating, the second hot
        tap water.
    """

    if gross_floor_area_m2 == 0:
        zeroes = constants(df_inputs, 0)
        return zeroes, zeroes

    every_xth = np.arange(0, n_rows, EVERY_X_HOURS)
    points_to_generate = len(every_xth)

    rng = np.random.default_rng(random_seed)
    std_dev = mock_data_constants['ResidentialHeatingRelativeErrorStdDev']
    generated_points = rng.normal(1, std_dev, points_to_generate)

    noise = np.empty((n_rows,))
    noise[:] = np.nan
    noise[every_xth] = generated_points

    nans, x = nan_helper(noise)
    noise[nans] = np.interp(x(nans), x(~nans), noise[~nans])

    space_heating_unscaled = df_inputs.select([pl.col('datetime'), pl.col('rad_energy').alias('value') * noise])
    hot_tap_water_unscaled = df_inputs.select([pl.col('datetime'), pl.col('hw_energy').alias('value') * noise])
    # Could argue we should use different noise here ^, but there is some logic to these two varying together

    # Scale
    space_heating_per_year_per_m2 = mock_data_constants['ResidentialSpaceHeatKwhPerYearM2']
    space_heating_scaled = scale_energy_consumption(space_heating_unscaled, gross_floor_area_m2,
                                                    space_heating_per_year_per_m2, n_rows)
    hot_tap_water_per_year_per_m2 = mock_data_constants['ResidentialHotTapWaterKwhPerYearM2']
    hot_tap_water_scaled = scale_energy_consumption(hot_tap_water_unscaled, gross_floor_area_m2,
                                                    hot_tap_water_per_year_per_m2, n_rows)
    return space_heating_scaled, hot_tap_water_scaled
