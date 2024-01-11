from typing import Any, Dict, Tuple

import numpy as np

import polars as pl

from statsmodels.regression.linear_model import RegressionResultsWrapper

from tradingplatformpoc.generate_data.generation_functions.common import scale_energy_consumption
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


def constants(df_inputs: pl.LazyFrame, val: float) -> pl.LazyFrame:
    return df_inputs.select([pl.col('datetime'), pl.lit(val).alias('value')])


def calculate_adjustment_for_energy_prev(model: RegressionResultsWrapper, energy_prev: float) -> float:
    """
    As described in https://doc.afdrift.se/display/RPJ/Household+electricity+mock-up, here we calculate an
    autoregressive adjustment to a simulation.
    @param model: A statsmodels.regression.linear_model.RegressionResultsWrapper, which must include parameters with the
        following names:
            'np.where(np.isnan(energy_prev), 0, energy_prev)'
            'np.where(np.isnan(energy_prev), 0, np.power(energy_prev, 2))'
            'np.where(np.isnan(energy_prev), 0, np.minimum(energy_prev, 0.3))'
            'np.where(np.isnan(energy_prev), 0, np.minimum(energy_prev, 0.7))'
    @param energy_prev: The simulated energy consumption in the previous time step (a.k.a. y_(t-1)
    @return: The autoregressive part of the simulated energy, as a float
    """
    return model.params['np.where(np.isnan(energy_prev), 0, energy_prev)'] * energy_prev + \
        model.params['np.where(np.isnan(energy_prev), 0, np.power(energy_prev, 2))'] * np.power(energy_prev, 2) + \
        model.params['np.where(np.isnan(energy_prev), 0, np.minimum(energy_prev, 0.3))'] * np.minimum(energy_prev,
                                                                                                      0.3) + \
        model.params['np.where(np.isnan(energy_prev), 0, np.minimum(energy_prev, 0.7))'] * np.minimum(energy_prev, 0.7)


def simulate_series(input_df: pl.DataFrame, rand_seed: int, model: RegressionResultsWrapper) -> pl.DataFrame:
    """
    Runs simulations using "model" and "input_df", with "rand_seed" as the random seed (can be specified, so that the
    experiment becomes reproducible, and also when simulating several different apartments/houses, the simulations don't
    end up identical).
    The fact that autoregressive parts are included in the model, makes it more difficult to predict with, we can't just
    use the predict-method. As explained in https://doc.afdrift.se/display/RPJ/Household+electricity+mock-up,
    we use the predict-method first and then add on autoregressive terms afterwards. The autoregressive parts are
    calculated in calculate_adjustment_for_energy_prev(...).
    :param input_df: pl.DataFrame
    :param rand_seed: int
    :param model: statsmodels.regression.linear_model.RegressionResultsWrapper
    :return: pl.DataFrame with 'datetime' and 'value', the latter being simulated energy
    """
    # Initialize 'energy_prev' with a np.nan first, then the rest 0s (for now)
    input_df = input_df.with_column(pl.concat([pl.lit(np.nan), pl.repeat(0, input_df.height - 1)]).alias('energy_prev'))

    # run regression with other_prev = 0, using the other_prev_start_dummy
    z_hat = model.predict(input_df.to_pandas())
    input_df = input_df.with_column(pl.from_pandas(z_hat).alias('z_hat'))
    std_dev = np.sqrt(model.scale)  # store standard error

    rng = np.random.default_rng(rand_seed)  # set random seed
    eps_vec = rng.normal(0, std_dev, size=input_df.height)

    # For t=0, z=y. For t>0, set y_t to np.nan for now
    simulated_log_energy_unscaled = [input_df[0, 'z_hat'] + eps_vec[0]]

    # For t>0, y_t = max(0, zhat_t + beta * y_(t-1) + eps_t)
    # This is slow!
    for t in range(1, len(input_df)):
        energy_prev = np.exp(simulated_log_energy_unscaled[t - 1])
        adjustment_for_prev = calculate_adjustment_for_energy_prev(model, energy_prev)
        simulated_log_energy_unscaled.append(input_df['z_hat'][t] + adjustment_for_prev + eps_vec[t])
    return input_df.select([pl.col('datetime'), pl.Series('value', simulated_log_energy_unscaled).exp()])


def simulate_household_electricity_aggregated(df_inputs: pl.LazyFrame, model: RegressionResultsWrapper,
                                              gross_floor_area_m2: float, start_seed: int, n_rows: int,
                                              kwh_per_year_m2_atemp: float) -> pl.LazyFrame:
    """
    Simulates the aggregated household electricity consumption for an area. Instead of simulating individual apartments,
    this method just sees the whole area as one apartment, and simulates that. This drastically reduces runtime.
    Mathematically, the sum of log-normal random variables is approximately log-normal, which supports this way of doing
    things. Furthermore, just simulating one series instead of ~100 (or however many apartments are in an area), should
    increase randomness. This is probably not a bad thing for us: Since our simulations stem from a model fit on one
    single apartment, increased randomness could actually be said to make a lot of sense.
    Returns a pl.DataFrame with the datetimes and the data.
    """
    if gross_floor_area_m2 == 0:
        return df_inputs.select([pl.col('datetime'), pl.lit(0).alias('value')])

    unscaled_simulated_values_for_area = simulate_series(df_inputs.collect(), start_seed, model)
    # Scale
    simulated_values_for_this_area = scale_energy_consumption(unscaled_simulated_values_for_area.lazy(),
                                                              gross_floor_area_m2, kwh_per_year_m2_atemp, n_rows)
    return simulated_values_for_this_area
