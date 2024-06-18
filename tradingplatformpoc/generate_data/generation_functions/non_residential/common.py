import datetime
from typing import Any, Callable, Dict, Tuple

import numpy as np

import polars as pl

from tradingplatformpoc.generate_data.generation_functions.common import scale_energy_consumption

# Binomial model coefficients
BM_INTERCEPT = 33.973192
BM_TEMP_1 = -2.012400
BM_TEMP_2 = -0.548222
BM_TEMP_3 = -0.880526
# Linear model coefficients
LM_INTERCEPT = 26.030581
LM_TEMP = -1.943567
LM_STD_DEV = 3.8660184261891652


# Space heating model
# ----------------------------------------------------------------------------------------------------------------------

def inv_logit(p):
    # Binomial GLM has the logit function as link
    return np.exp(p) / (1 + np.exp(p))


def probability_of_0_space_heating(temperature: float) -> float:
    # No observations of 0 energy where temperature is < 5.5. Therefore, to not get random 0s for much lower
    # temperatures than this, we'll artificially set heating to be non-zero whenever temperature < 5.5.
    # Also, no observations of >0 energy where temperature is > 18.7. Therefore, we set heating to be 0 whenever
    # temperature >= 20.
    if temperature < 5.5:  # Changed from 5 since Andreas @ BDAB thought we had too many 0s during winter months
        return 0.0
    elif temperature >= 20:
        return 1.0
    else:
        return 1.0 - inv_logit(BM_INTERCEPT
                               + BM_TEMP_1 * min(max(temperature, 5.5), 8)
                               + BM_TEMP_2 * min(max(temperature, 8), 12.5)
                               + BM_TEMP_3 * max(temperature, 12.5))


def space_heating_given_more_than_0(temperature: float) -> float:
    """
    If we have concluded that the heating energy use is > 0, then we use this model to predict how much it will be.
    """
    return max(0.0, LM_INTERCEPT + LM_TEMP * temperature)


# ----------------------------------------------------------------------------------------------------------------------

def simulate_hot_tap_water(school_atemp_m2: float, random_seed: int, input_df: pl.LazyFrame,
                           space_heating_per_year_m2: float, time_factor_function: Callable,
                           relative_error_std_dev: float, n_rows: int) -> pl.LazyFrame:
    """
    Gets a factor based on the hour of day, multiplies it by a noise-factor, and scales it. Parameter 'input_df'
    should be a pl.DataFrame with a column called 'datetime'.
    @return A pl.DataFrame with hot tap water load for the area, scaled to KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL.
    """
    rng = np.random.default_rng(random_seed)

    lf = input_df.select(pl.col('datetime')).with_column(
        pl.col('datetime').apply(time_factor_function).alias('time_factors')
    )

    lf = lf.with_column(pl.Series(name='relative_errors',
                                  values=rng.normal(0, relative_error_std_dev, n_rows)))
    lf = lf.with_column(
        (pl.col('time_factors') * (1 + pl.col('relative_errors'))).alias('unscaled_values')
    )
    # Evaluate the lazy data frame
    lf = lf.select([pl.col('datetime'), pl.col('unscaled_values').alias('value')])

    scaled_series = scale_energy_consumption(lf, school_atemp_m2,
                                             space_heating_per_year_m2, n_rows)
    return scaled_series


def simulate_space_heating(atemp_m2: float, random_seed: int,
                           lazy_inputs: pl.LazyFrame, space_heating_per_year_m2: float,
                           time_factor_function: Callable, n_rows: int) -> pl.LazyFrame:
    """
    For more information, see "docs/Non-residential heating mock-up.md"
    @input input_df: A pl.DataFrame with a 'datetime' column and a 'temperature' column
    @return A pl.DataFrame with datetime and space heating load for the area, scaled to
        space_heating_per_year_m2.
    """
    rng = np.random.default_rng(random_seed)

    # First calculate probability that there is 0 heating demand, then simulate.
    # Then, if heat demand non-zero, how much is it? Calculate expectancy then simulate
    lf = lazy_inputs.select(
        [pl.col('datetime'),
         pl.when(
             pl.col('temperature').
             apply(lambda x: probability_of_0_space_heating(x)).
             apply(lambda x: rng.binomial(n=1, p=1 - x)) == 1
        ).then(
             pl.col('temperature').
             apply(lambda x: space_heating_given_more_than_0(x)).
             apply(lambda x: np.maximum(0, rng.normal(loc=x, scale=LM_STD_DEV)))
        ).otherwise(0).alias('sim_energy_unscaled_no_time_factor')
        ]
    )

    # Adjust for opening times
    lf = lf.with_column(
        pl.col('datetime').apply(time_factor_function).alias('time_factors')
    ).with_column(
        (pl.col('sim_energy_unscaled_no_time_factor') * pl.col('time_factors')).alias('sim_energy_unscaled')
    )

    # Scale
    scaled_df = scale_energy_consumption(lf.select([pl.col('datetime'), pl.col('sim_energy_unscaled').alias('value')]),
                                         atemp_m2,
                                         space_heating_per_year_m2, n_rows)

    return scaled_df


def simulate_area_electricity(atemp_m2: float, random_seed: int,
                              input_df: pl.LazyFrame, kwh_elec_per_yr_per_m2: float,
                              rel_error_std_dev: float,
                              hourly_level_function: Callable[[datetime.datetime], float], n_rows: int) -> pl.LazyFrame:
    """
    Simulates electricity demand for the given datetimes. Uses random_seed when generating random numbers.
    The total yearly amount is calculated using atemp_m2 and kwh_elec_per_yr_per_m2. Variability over time is
    calculated using hourly_level_function and noise is added, its quantity determined by rel_error_std_dev.
    For more information, see "docs/Non-residential electricity mock-up.md".
    @return A pl.DataFrame with datetimes and hourly electricity consumption, in kWh.
    """
    rng = np.random.default_rng(random_seed)
    lf = input_df.select(pl.col('datetime')).with_column(
        pl.col('datetime').apply(hourly_level_function).alias('time_factors')
    )
    lf = lf.with_column(pl.Series(name='relative_errors',
                                  values=rng.normal(0, rel_error_std_dev, n_rows)))
    lf = lf.with_column(
        (pl.col('time_factors') * (1 + pl.col('relative_errors'))).alias('unscaled_values')
    )
    lf = lf.select([pl.col('datetime'), pl.col('unscaled_values').alias('value')])
    scaled_series = scale_energy_consumption(lf, atemp_m2, kwh_elec_per_yr_per_m2, n_rows)
    return scaled_series


def get_cooling_month_scaling_factor(month: int) -> float:
    """
    Returns a dimensionless scaling factor. Values from BDAB (Energislag_Timvärden_Jonstaka_underlag Afry 231115.xlsx)
    """
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


def simulate_heating(mock_data_constants: Dict[str, Any], atemp_m2: float, space_heat_constant_name: str,
                     hot_water_constant_name: str, time_factor_function: Callable, random_seed: int,
                     input_df: pl.LazyFrame, n_rows: int) -> Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    For more information, see "docs/Non-residential heating mock-up.md".
    @return Two pl.LazyFrames with datetimes and hourly heating load, in kWh. The first space heating, the second hot
        tap water.
    """
    space_heating_per_year_m2 = mock_data_constants[space_heat_constant_name]
    space_heating = simulate_space_heating(atemp_m2, random_seed, input_df,
                                           space_heating_per_year_m2,
                                           time_factor_function, n_rows)
    hot_tap_water_per_year_m2 = mock_data_constants[hot_water_constant_name]
    hot_tap_water_relative_error_std_dev = mock_data_constants['RelativeErrorStdDev']
    hot_tap_water = simulate_hot_tap_water(atemp_m2, random_seed, input_df,
                                           hot_tap_water_per_year_m2,
                                           time_factor_function,
                                           hot_tap_water_relative_error_std_dev,
                                           n_rows)
    return space_heating, hot_tap_water


def simulate_cooling(atemp_m2: float, kwh_cooling_per_yr_per_m2: float,
                     rel_error_std_dev: float, time_factor_function: Callable,
                     random_seed: int, input_df: pl.LazyFrame, n_rows: int) \
        -> pl.LazyFrame:
    rng = np.random.default_rng(random_seed)
    lf = input_df.select(
        [pl.col('datetime'), pl.col('datetime').apply(time_factor_function).alias('time_factors')])
    lf = lf.with_column(pl.Series(name='relative_errors',
                                  values=rng.normal(0, rel_error_std_dev, n_rows)))
    lf = lf.with_column(
        (pl.col('time_factors') * (1 + pl.col('relative_errors'))).alias('value')
    )
    return scale_energy_consumption(lf, atemp_m2, kwh_cooling_per_yr_per_m2, n_rows)
