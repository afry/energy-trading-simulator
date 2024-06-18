from typing import Any, Dict, Tuple

import polars as pl

from tradingplatformpoc.generate_data.generation_functions.common import constants, get_noise, scale_energy_consumption


def simulate_residential_total_heating(mock_data_constants: Dict[str, Any], df_inputs: pl.LazyFrame, n_rows: int,
                                       atemp_m2: float, random_seed: int) -> \
        Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    Following along with "docs/Residential heating mock-up.md".

    df_inputs needs to contain 'rad_energy' and 'hw_energy' columns, with the Vetelangden data.
    Returns two pl.LazyFrames with datetimes and simulated data: The first representing space heating, the second hot
        tap water.
    """

    if atemp_m2 == 0:
        zeroes = constants(df_inputs, 0)
        return zeroes, zeroes

    noise = get_noise(n_rows, random_seed, mock_data_constants['RelativeErrorStdDev'])

    space_heating_unscaled = df_inputs.select([pl.col('datetime'), pl.col('rad_energy').alias('value') * noise])
    hot_tap_water_unscaled = df_inputs.select([pl.col('datetime'), pl.col('hw_energy').alias('value') * noise])
    # Could argue we should use different noise here ^, but there is some logic to these two varying together

    # Scale
    space_heating_per_year_per_m2 = mock_data_constants['ResidentialSpaceHeatKwhPerYearM2']
    space_heating_scaled = scale_energy_consumption(space_heating_unscaled, atemp_m2,
                                                    space_heating_per_year_per_m2, n_rows)
    hot_tap_water_per_year_per_m2 = mock_data_constants['ResidentialHotTapWaterKwhPerYearM2']
    hot_tap_water_scaled = scale_energy_consumption(hot_tap_water_unscaled, atemp_m2,
                                                    hot_tap_water_per_year_per_m2, n_rows)
    return space_heating_scaled, hot_tap_water_scaled
