import datetime
import hashlib
import json
import logging
import os
import pickle
import time
from typing import Any, Callable, Dict, Tuple, Union

import numpy as np
import pandas as pd

import polars as pl

from pkg_resources import resource_filename

import statsmodels.api as sm
from statsmodels.regression.linear_model import RegressionResultsWrapper

from tradingplatformpoc import commercial_heating_model
from tradingplatformpoc.mock_data_generation_functions import MockDataKey, get_all_building_agents, \
    get_commercial_electricity_consumption_hourly_factor, \
    get_commercial_heating_consumption_hourly_factor, \
    get_elec_cons_key, get_hot_tap_water_cons_key, get_pv_prod_key, \
    get_school_heating_consumption_hourly_factor, get_space_heat_cons_key, load_existing_data_sets
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod, get_if_exists_else, nan_helper

CONFIG_FILE = 'default_config.json'

DATA_PATH = 'tradingplatformpoc.data'

MOCK_DATAS_PICKLE = resource_filename(DATA_PATH, 'mock_datas.pickle')

KWH_PER_YEAR_M2_ATEMP = 20  # According to Skanska: 20 kWh/year/m2 Atemp
M2_PER_APARTMENT = 70
# Will use this to set random seed.
RESIDENTIAL_HEATING_SEED_SUFFIX = "RH"
EVERY_X_HOURS = 3  # Random noise will be piecewise linear, with knots every X hours
HEATING_RELATIVE_ERROR_STD_DEV = 0.2
# For the following two, see https://doc.afdrift.se/display/RPJ/Expected+energy+use+for+different+buildings
KWH_PER_YEAR_M2_RESIDENTIAL_SPACE_HEATING = 25
KWH_PER_YEAR_M2_RESIDENTIAL_HOT_TAP_WATER = 25
# Constants for the 'commercial' electricity bit:
COMMERCIAL_ELECTRICITY_SEED_SUFFIX = "CE"
KWH_ELECTRICITY_PER_YEAR_M2_COMMERCIAL = 118
COMMERCIAL_ELECTRICITY_RELATIVE_ERROR_STD_DEV = 0.2
# Constants for the 'commercial' heating bit:
COMMERCIAL_HEATING_SEED_SUFFIX = "CH"
# As per https://doc.afdrift.se/display/RPJ/Commercial+areas
KWH_SPACE_HEATING_PER_YEAR_M2_COMMERCIAL = 32
KWH_HOT_TAP_WATER_PER_YEAR_M2_COMMERCIAL = 3.5
COMMERCIAL_HOT_TAP_WATER_RELATIVE_ERROR_STD_DEV = 0.2
# Constants for school
SCHOOL_HEATING_SEED_SUFFIX = "SH"
SCHOOL_ELECTRICITY_SEED_SUFFIX = "SE"
KWH_ELECTRICITY_PER_YEAR_M2_SCHOOL = 60
SCHOOL_ELECTRICITY_RELATIVE_ERROR_STD_DEV = 0.2
SCHOOL_HOT_TAP_WATER_RELATIVE_ERROR_STD_DEV = 0.2
# For the following two, see https://doc.afdrift.se/display/RPJ/Expected+energy+use+for+different+buildings
KWH_HOT_TAP_WATER_PER_YEAR_M2_SCHOOL = 7
KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL = 25

"""
This script generates the following, for BuildingAgents:
*Household electricity consumption data
*Commercial electricity consumption data
*Residential hot water consumption data
*Commercial hot water consumption data
*Residential space heating consumption data
*Commercial space heating consumption data
*Rooftop PV production data
It stores such data in the MOCK_DATAS_PICKLE file, as a dictionary, where the set of BuildingAgents used to generate the
data is the key, and a pl.DataFrame of generated data is the value. This way, simulation_runner can get the correct mock
data set for the given config.
For some more information: https://doc.afdrift.se/display/RPJ/Household+electricity+mock-up
"""

logger = logging.getLogger(__name__)


def run(config_data: Dict[str, Any]) -> Dict[MockDataKey, pl.DataFrame]:
    # Load pre-existing mock data sets
    all_data_sets = load_existing_data_sets(MOCK_DATAS_PICKLE)

    building_agents, total_gross_floor_area_residential = get_all_building_agents(config_data["Agents"])
    default_pv_efficiency = config_data["AreaInfo"]["DefaultPVEfficiency"]
    mock_data_key = MockDataKey(frozenset(building_agents), default_pv_efficiency)

    # # Need to freeze, else can't use it as key in dict
    # building_agents_frozen_set = frozenset(building_agents)

    if mock_data_key in all_data_sets:
        logger.info('Already had mock data for the configuration described in %s, exiting generate_mock_data' %
                    CONFIG_FILE)
    else:
        # So we have established that we need to generate new mock data.
        logger.debug('Beginning mock data generation')
        # Load model
        model = sm.load(resource_filename(DATA_PATH, 'models/household_electricity_model.pickle'))
        logger.debug('Model loaded')

        # Read in-data: Temperature and timestamps
        df_inputs, df_irrd = create_inputs_df(resource_filename(DATA_PATH, 'temperature_vetelangden.csv'),
                                              resource_filename(DATA_PATH, 'varberg_irradiation_W_m2_h.csv'),
                                              resource_filename(DATA_PATH, 'vetelangden_slim.csv'))

        logger.debug('Input dataframes created')
        output_per_building = pl.DataFrame({'datetime': df_inputs['datetime']})
        logger.debug('Output dataframes created')

        n_rows = df_inputs.height
        lazy_inputs = df_inputs.lazy()

        total_time_elapsed = 0.0
        n_areas_done = 0
        n_areas = len(building_agents)
        logger.debug('{} areas to iterate over'.format(n_areas))
        for agent in building_agents:

            agent_dict = dict(agent)
            logger.debug('Generating new data for ' + agent_dict['Name'])
            output_per_building, time_elapsed = simulate_and_add_to_output_df(agent_dict, lazy_inputs, n_rows, df_irrd,
                                                                              default_pv_efficiency, model,
                                                                              output_per_building, all_data_sets)
            n_areas_done = n_areas_done + 1
            n_areas_remaining = n_areas - n_areas_done
            total_time_elapsed = total_time_elapsed + time_elapsed
            if n_areas_remaining > 0:
                time_taken_per_area = total_time_elapsed / n_areas_done
                estimated_time_left = n_areas_remaining * time_taken_per_area
                logger.info('Estimated time left: {:.2f} seconds'.format(estimated_time_left))

        all_data_sets[mock_data_key] = output_per_building
        pickle.dump(all_data_sets, open(MOCK_DATAS_PICKLE, 'wb'))
    return all_data_sets


def simulate_and_add_to_output_df(agent: dict, df_inputs: pl.LazyFrame, n_rows: int, df_irrd: pl.DataFrame,
                                  default_pv_efficiency: float, model: RegressionResultsWrapper,
                                  output_per_actor: pl.DataFrame, all_data_sets: dict) -> Tuple[pl.DataFrame, float]:
    start = time.time()
    agent = dict(agent)  # "Unfreezing" the frozenset
    logger.debug('Starting work on \'{}\''.format(agent['Name']))
    pv_area = get_if_exists_else(agent, 'PVArea', 0)

    pre_existing_data = find_agent_in_other_data_sets(agent, all_data_sets, default_pv_efficiency)
    # 'diagonal' here means that columns that only exist in one of the dataframes will be included, and filled with null
    output_per_actor = pl.concat((output_per_actor, pre_existing_data), how='diagonal')

    if (not get_elec_cons_key(agent['Name']) in output_per_actor.columns) or \
            (not get_space_heat_cons_key(agent['Name']) in output_per_actor.columns) or \
            (not get_hot_tap_water_cons_key(agent['Name']) in output_per_actor.columns):
        seed_residential_electricity = calculate_seed_from_string(agent['Name'])
        seed_residential_heating = calculate_seed_from_string(agent['Name'] + RESIDENTIAL_HEATING_SEED_SUFFIX)
        seed_commercial_electricity = calculate_seed_from_string(agent['Name'] + COMMERCIAL_ELECTRICITY_SEED_SUFFIX)
        seed_commercial_heating = calculate_seed_from_string(agent['Name'] + COMMERCIAL_HEATING_SEED_SUFFIX)
        seed_school_electricity = calculate_seed_from_string(agent['Name'] + SCHOOL_ELECTRICITY_SEED_SUFFIX)
        seed_school_heating = calculate_seed_from_string(agent['Name'] + SCHOOL_HEATING_SEED_SUFFIX)
        fraction_commercial = get_if_exists_else(agent, 'FractionCommercial', 0)
        fraction_school = get_if_exists_else(agent, 'FractionSchool', 0)
        logger.debug("Total non-residential fraction {}".format(fraction_commercial + fraction_school))
        if fraction_school + fraction_commercial > 1:
            logger.error("Total non-residential fractions for agent {} larger than 100%".format(agent["Name"]))
            exit(1)
        fraction_residential = 1.0 - fraction_commercial - fraction_school
        commercial_gross_floor_area = agent['GrossFloorArea'] * fraction_commercial
        residential_gross_floor_area = agent['GrossFloorArea'] * fraction_residential
        school_gross_floor_area_m2 = agent['GrossFloorArea'] * fraction_school

        commercial_electricity_cons = simulate_area_electricity(
            commercial_gross_floor_area,
            seed_commercial_electricity,
            df_inputs,
            KWH_ELECTRICITY_PER_YEAR_M2_COMMERCIAL,
            COMMERCIAL_ELECTRICITY_RELATIVE_ERROR_STD_DEV,
            get_commercial_electricity_consumption_hourly_factor,
            n_rows)
        commercial_space_heating_cons, commercial_hot_tap_water_cons = \
            simulate_commercial_area_total_heating(commercial_gross_floor_area, seed_commercial_heating, df_inputs,
                                                   n_rows)

        residential_space_heating_cons, residential_hot_tap_water_cons = \
            simulate_residential_total_heating(df_inputs, n_rows, residential_gross_floor_area,
                                               seed_residential_heating)

        household_electricity_cons = simulate_household_electricity_aggregated(
            df_inputs, model, residential_gross_floor_area, seed_residential_electricity, n_rows)

        school_electricity_cons = simulate_area_electricity(school_gross_floor_area_m2, seed_school_electricity,
                                                            df_inputs, KWH_ELECTRICITY_PER_YEAR_M2_SCHOOL,
                                                            SCHOOL_ELECTRICITY_RELATIVE_ERROR_STD_DEV,
                                                            get_school_heating_consumption_hourly_factor, n_rows)
        school_space_heating_cons, school_hot_tap_water_cons = \
            simulate_school_area_heating(school_gross_floor_area_m2, seed_school_heating, df_inputs, n_rows)
        logger.debug("Adding output for agent {}".format(agent['Name']))

        output_per_actor = output_per_actor.\
            join(add_datetime_value_frames(commercial_electricity_cons,
                                           household_electricity_cons,
                                           school_electricity_cons),
                 on='datetime').\
            rename({'value': get_elec_cons_key(agent['Name'])}).\
            join(add_datetime_value_frames(commercial_space_heating_cons,
                                           residential_space_heating_cons,
                                           school_space_heating_cons),
                 on='datetime').\
            rename({'value': get_space_heat_cons_key(agent['Name'])}).\
            join(add_datetime_value_frames(commercial_hot_tap_water_cons,
                                           residential_hot_tap_water_cons,
                                           school_hot_tap_water_cons),
                 on='datetime').\
            rename({'value': get_hot_tap_water_cons_key(agent['Name'])})

    if not get_pv_prod_key(agent['Name']) in output_per_actor.columns:
        pv_efficiency = get_if_exists_else(agent, 'PVEfficiency', default_pv_efficiency)
        prod = pl.DataFrame({'datetime': df_irrd['datetime'], get_pv_prod_key(agent['Name']):
                            calculate_solar_prod(df_irrd['irradiation'], pv_area, pv_efficiency)})
        output_per_actor = output_per_actor.join(prod, on='datetime')

    end = time.time()
    time_elapsed = end - start
    logger.debug('Finished work on \'{}\', took {:.2f} seconds'.format(agent['Name'], time_elapsed))
    return output_per_actor, time_elapsed


def add_datetime_value_frames(*dfs: Union[pl.DataFrame, pl.LazyFrame]) -> Union[pl.DataFrame, pl.LazyFrame]:
    """Works on both DataFrame and LazyFrame"""
    if len(dfs) == 1:
        return dfs[0]
    else:
        base_df = dfs[0]
        for i in range(1, len(dfs)):
            base_df = base_df.join(dfs[i], on='datetime').\
                select([pl.col('datetime'), (pl.col('value') + pl.col('value_right')).alias('value')])
        return base_df


def simulate_household_electricity_aggregated(df_inputs: pl.LazyFrame, model: RegressionResultsWrapper,
                                              gross_floor_area_m2: float, start_seed: int, n_rows: int) -> pl.LazyFrame:
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
                                                              gross_floor_area_m2, KWH_PER_YEAR_M2_ATEMP, n_rows)
    return simulated_values_for_this_area


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
    # input_df = input_df.with_column(pl.concat([pl.lit(input_df[0, 'z_hat'] + eps_vec[0]),
    #                                 pl.repeat(np.nan, input_df.height - 1)]).
    #                                 alias('simulated_log_energy_unscaled'))

    # For t>0, y_t = max(0, zhat_t + beta * y_(t-1) + eps_t)
    # This is slow!
    for t in range(1, len(input_df)):
        energy_prev = np.exp(simulated_log_energy_unscaled[t - 1])
        adjustment_for_prev = calculate_adjustment_for_energy_prev(model, energy_prev)
        simulated_log_energy_unscaled.append(input_df['z_hat'][t] + adjustment_for_prev + eps_vec[t])
    return input_df.select([pl.col('datetime'), pl.Series('value', simulated_log_energy_unscaled).exp()])


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
           model.params['np.where(np.isnan(energy_prev), 0, np.minimum(energy_prev, 0.7))'] * np.minimum(energy_prev,
                                                                                                         0.7)


def create_inputs_df(temperature_csv_path: str, irradiation_csv_path: str, heating_csv_path: str) -> \
        Tuple[pl.DataFrame, pl.DataFrame]:
    """
    Create pl.DataFrames with certain columns that are needed to predict from the household electricity linear model.
    Will start reading CSVs as pd.DataFrames, since pandas is better at handling time zones, and then convert to polars.
    @param temperature_csv_path: Path to a CSV-file with datetime-stamps and temperature readings, in degrees C.
    @param irradiation_csv_path: Path to a CSV-file with datetime-stamps and solar irradiance readings, in W/m2.
    @param heating_csv_path: Path to a CSV-file with datetime-stamps and heating energy readings, in kW.
    @return: Two pl.DataFrames:
        The first one contains date/time-related columns, as well as outdoor temperature readings and heating energy
            demand data from Vetelangden. This dataframe will be used to simulate electricity and heat demands.
        The second one contains irradiation data, which is used to estimate PV production.
    """
    df_temp = pd.read_csv(temperature_csv_path, names=['datetime', 'temperature'],
                          delimiter=';', header=0)
    df_temp['datetime'] = pd.to_datetime(df_temp['datetime'])
    # The input is in local time, with NA for the times that "don't exist" due to daylight savings time
    df_temp['datetime'] = df_temp['datetime'].dt.tz_localize('Europe/Stockholm', nonexistent='NaT', ambiguous='NaT')
    # Now, remove the rows where datetime is NaT (the values there are NA anyway)
    df_temp = df_temp.loc[~df_temp['datetime'].isnull()]
    # Finally, convert to UTC
    df_temp['datetime'] = df_temp['datetime'].dt.tz_convert('UTC')

    df_irrd = pd.read_csv(irradiation_csv_path)
    df_irrd['datetime'] = pd.to_datetime(df_irrd['datetime'], utc=True)
    # This irradiation data is in UTC, so we don't need to convert it.

    df_inputs = df_temp.merge(df_irrd)
    # In case there are any missing values
    df_inputs[['temperature', 'irradiation']] = df_inputs[['temperature', 'irradiation']].interpolate(method='linear')
    df_inputs['hour_of_day'] = df_inputs['datetime'].dt.hour + 1
    df_inputs['day_of_week'] = df_inputs['datetime'].dt.dayofweek + 1
    df_inputs['day_of_month'] = df_inputs['datetime'].dt.day
    df_inputs['month_of_year'] = df_inputs['datetime'].dt.month
    df_inputs['major_holiday'] = df_inputs['datetime'].apply(lambda dt: is_major_holiday_sweden(dt))
    df_inputs['pre_major_holiday'] = df_inputs['datetime'].apply(lambda dt: is_day_before_major_holiday_sweden(dt))
    df_inputs.set_index('datetime', inplace=True)

    df_heat = pd.read_csv(heating_csv_path, names=['datetime', 'rad_energy', 'hw_energy'], header=0)
    df_heat['datetime'] = pd.to_datetime(df_heat['datetime'])
    # The input is in local time, a bit unclear about times that "don't exist" when DST starts, or "exist twice" when
    # DST ends - will remove such rows, they have some NAs and stuff anyway
    df_heat['datetime'] = df_heat['datetime'].dt.tz_localize('Europe/Stockholm', nonexistent='NaT', ambiguous='NaT')
    df_heat = df_heat.loc[~df_heat['datetime'].isnull()]
    # Finally, convert to UTC
    df_heat['datetime'] = df_heat['datetime'].dt.tz_convert('UTC')

    df_heat.set_index('datetime', inplace=True)

    df_inputs = df_inputs.merge(df_heat, left_index=True, right_index=True)

    return pl.from_pandas(df_inputs.reset_index()), pl.from_pandas(df_irrd)


def is_major_holiday_sweden(timestamp: pd.Timestamp):
    swedish_time = timestamp.tz_convert("Europe/Stockholm")
    month_of_year = swedish_time.month
    day_of_month = swedish_time.day
    # Major holidays will naturally have a big impact on household electricity usage patterns, with people not working
    # etc. Included here are: Christmas eve, Christmas day, Boxing day, New years day, epiphany, 1 may, national day.
    # Some moveable ones not included (Easter etc)
    return ((month_of_year == 12) & (day_of_month == 24)) | \
           ((month_of_year == 12) & (day_of_month == 25)) | \
           ((month_of_year == 12) & (day_of_month == 26)) | \
           ((month_of_year == 1) & (day_of_month == 1)) | \
           ((month_of_year == 1) & (day_of_month == 6)) | \
           ((month_of_year == 5) & (day_of_month == 1)) | \
           ((month_of_year == 6) & (day_of_month == 6))


def is_day_before_major_holiday_sweden(timestamp: pd.Timestamp):
    swedish_time = timestamp.tz_convert("Europe/Stockholm")
    month_of_year = swedish_time.month
    day_of_month = swedish_time.day
    # Major holidays will naturally have a big impact on household electricity usage patterns, with people not working
    # etc. Included here are:
    # Day before christmas eve, New years eve, day before epiphany, Valborg, day before national day.
    return ((month_of_year == 12) & (day_of_month == 23)) | \
           ((month_of_year == 12) & (day_of_month == 31)) | \
           ((month_of_year == 1) & (day_of_month == 5)) | \
           ((month_of_year == 4) & (day_of_month == 30)) | \
           ((month_of_year == 6) & (day_of_month == 5))


def scale_energy_consumption(unscaled_simulated_values_kwh: pl.LazyFrame, m2: float,
                             kwh_per_year_per_m2: float, n_rows: int) -> pl.LazyFrame:
    if n_rows > 8760:
        # unscaled_simulated_values may contain more than 1 year, so just look at the first 8766 hours (365.25 days)
        return unscaled_simulated_values_kwh.\
            with_column(pl.Series('incr', range(1, n_rows + 1))).\
            select([pl.col('datetime'),
                    pl.col('value') * m2 * kwh_per_year_per_m2 / pl.col('value').where(pl.col('incr') <= 8766).sum()])
    else:
        raise RuntimeError("Less than a year's worth of data!")


def simulate_area_electricity(gross_floor_area_m2: float, random_seed: int,
                              input_df: pl.LazyFrame, kwh_elec_per_yr_per_m2: float,
                              rel_error_std_dev: float,
                              hourly_level_function: Callable[[datetime.datetime], float], n_rows: int) -> pl.LazyFrame:
    """
    Simulates electricity demand for the given datetimes. Uses random_seed when generating random numbers.
    The total yearly amount is calculated using gross_floor_area_m2 and kwh_elec_per_yr_per_m2. Variability over time is
    calculated using hourly_level_function and noise is added, its quantity determined by rel_error_std_dev.
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas
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
    scaled_series = scale_energy_consumption(lf, gross_floor_area_m2, kwh_elec_per_yr_per_m2, n_rows)
    return scaled_series


def simulate_commercial_area_total_heating(commercial_gross_floor_area_m2: float, random_seed: int,
                                           input_df: pl.LazyFrame, n_rows: int) -> Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas and
    https://doc.afdrift.se/display/RPJ/Coop+heating+energy+use+mock-up
    @return Two pl.LazyFrames with datetimes and hourly heating load, in kWh. The first space heating, the second hot
        tap water.
    """
    space_heating = simulate_space_heating(commercial_gross_floor_area_m2, random_seed, input_df,
                                           KWH_SPACE_HEATING_PER_YEAR_M2_COMMERCIAL,
                                           get_commercial_heating_consumption_hourly_factor, n_rows)
    hot_tap_water = simulate_hot_tap_water(commercial_gross_floor_area_m2, random_seed, input_df,
                                           KWH_HOT_TAP_WATER_PER_YEAR_M2_COMMERCIAL,
                                           get_commercial_heating_consumption_hourly_factor, n_rows)
    return space_heating, hot_tap_water


def simulate_hot_tap_water(school_gross_floor_area_m2: float, random_seed: int, input_df: pl.LazyFrame,
                           space_heating_per_year_m2: float,
                           time_factor_function: Callable, n_rows: int) -> pl.LazyFrame:
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
                                  values=rng.normal(0, SCHOOL_HOT_TAP_WATER_RELATIVE_ERROR_STD_DEV, n_rows)))
    lf = lf.with_column(
        (pl.col('time_factors') * (1 + pl.col('relative_errors'))).alias('unscaled_values')
    )
    # Evaluate the lazy data frame
    lf = lf.select([pl.col('datetime'), pl.col('unscaled_values').alias('value')])

    scaled_series = scale_energy_consumption(lf, school_gross_floor_area_m2,
                                             space_heating_per_year_m2, n_rows)
    return scaled_series


def simulate_school_area_heating(school_gross_floor_area_m2: float, random_seed: int,
                                 input_df: pl.LazyFrame, n_rows: int) -> Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    This function follows the recipe outlined in the corresponding function for commercial buildings.
    @return Two pl.DataFrames with datetimes and hourly total heating load, in kWh.
    """
    space_heating = simulate_space_heating(school_gross_floor_area_m2, random_seed, input_df,
                                           KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL,
                                           get_school_heating_consumption_hourly_factor, n_rows)
    hot_tap_water = simulate_hot_tap_water(school_gross_floor_area_m2, random_seed, input_df,
                                           KWH_HOT_TAP_WATER_PER_YEAR_M2_SCHOOL,
                                           get_school_heating_consumption_hourly_factor, n_rows)
    return space_heating, hot_tap_water


def simulate_space_heating(school_gross_floor_area_m2: float, random_seed: int,
                           input_df: pl.LazyFrame, space_heating_per_year_m2: float,
                           time_factor_function: Callable, n_rows: int) -> pl.LazyFrame:
    """
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas and
    https://doc.afdrift.se/display/RPJ/Coop+heating+energy+use+mock-up
    @input input_df: A pl.DataFrame with a 'datetime' column and a 'temperature' column
    @return A pl.DataFrame with datetime and space heating load for the area, scaled to
        space_heating_per_year_m2.
    """
    rng = np.random.default_rng(random_seed)

    # First calculate probability that there is 0 heating demand, then simulate.
    # Then, if heat demand non-zero, how much is it? Calculate expectancy then simulate
    lf = input_df.lazy().select(
        [pl.col('datetime'),
            pl.col('temperature').
            apply(lambda x: commercial_heating_model.probability_of_0_space_heating(x)).
            apply(lambda x: np.random.binomial(n=1, p=1 - x)).alias('has_heat_demand'),
         pl.col('temperature').
            apply(lambda x: commercial_heating_model.space_heating_given_more_than_0(x)).
            apply(lambda x: np.maximum(0, rng.normal(loc=x, scale=commercial_heating_model.LM_STD_DEV))).alias(
            'heat_given_non_0')
         ])

    # Combine the above
    lf = lf.with_column(
        pl.when(pl.col('has_heat_demand') == 1).then(pl.col('heat_given_non_0')).otherwise(0).
        alias('sim_energy_unscaled_no_time_factor')
    )

    # Adjust for opening times
    lf = lf.with_column(
        pl.col('datetime').apply(time_factor_function).alias('time_factors')
    ).with_column(
        (pl.col('sim_energy_unscaled_no_time_factor') * pl.col('time_factors')).alias('sim_energy_unscaled')
    )

    # Scale
    scaled_df = scale_energy_consumption(lf.select([pl.col('datetime'), pl.col('sim_energy_unscaled').alias('value')]),
                                         school_gross_floor_area_m2,
                                         space_heating_per_year_m2, n_rows)

    return scaled_df


def simulate_residential_total_heating(df_inputs: pl.LazyFrame, n_rows: int, gross_floor_area_m2: float,
                                       random_seed: int) -> Tuple[pl.LazyFrame, pl.LazyFrame]:
    """
    Following along with https://doc.afdrift.se/display/RPJ/Jonstaka+heating+mock-up
    But as for electricity, we'll just see the whole sub-area as 1 house, shouldn't matter too much.
    df_inputs needs to contain 'rad_energy' and 'hw_energy' columns, with the Vetelangden data.
    Returns two pl.LazyFrames with datetimes and simulated data: The first representing space heating, the second hot
        tap water.
    """

    if gross_floor_area_m2 == 0:
        zeroes = df_inputs.select([pl.col('datetime'), pl.lit(0).alias('value')]).lazy()
        return zeroes, zeroes

    every_xth = np.arange(0, n_rows, EVERY_X_HOURS)
    points_to_generate = len(every_xth)

    rng = np.random.default_rng(random_seed)
    generated_points = rng.normal(1, HEATING_RELATIVE_ERROR_STD_DEV, points_to_generate)

    noise = np.empty((n_rows,))
    noise[:] = np.nan
    noise[every_xth] = generated_points

    nans, x = nan_helper(noise)
    noise[nans] = np.interp(x(nans), x(~nans), noise[~nans])

    space_heating_unscaled = df_inputs.lazy().select([pl.col('datetime'), pl.col('rad_energy').alias('value') * noise])
    hot_tap_water_unscaled = df_inputs.lazy().select([pl.col('datetime'), pl.col('hw_energy').alias('value') * noise])
    # Could argue we should use different noise here ^, but there is some logic to these two varying together

    # Scale using BDAB's estimate
    space_heating_scaled = scale_energy_consumption(space_heating_unscaled, gross_floor_area_m2,
                                                    KWH_PER_YEAR_M2_RESIDENTIAL_SPACE_HEATING, n_rows)
    hot_tap_water_scaled = scale_energy_consumption(hot_tap_water_unscaled, gross_floor_area_m2,
                                                    KWH_PER_YEAR_M2_RESIDENTIAL_HOT_TAP_WATER, n_rows)
    return space_heating_scaled, hot_tap_water_scaled


def find_agent_in_other_data_sets(agent_dict: Dict[str, Any], all_data_sets: Dict[MockDataKey, pl.DataFrame],
                                  default_pv_efficiency: float) -> pl.DataFrame:
    """Introduced in RES-216 - looking through other data sets, if this agent was present there, we can re-use that,
    instead of running the generation step again. This saves time. If no usable data is found, the returned DataFrame
    will be empty."""
    data_to_reuse = pl.DataFrame()
    found_prod_data = False
    found_cons_data = False
    for mock_data_key, mock_data in all_data_sets.items():
        set_of_building_agents = mock_data_key.building_agents_frozen_set
        other_default_pv_eff = mock_data_key.default_pv_efficiency
        for other_agent in set_of_building_agents:
            other_agent_dict = dict(other_agent)
            if (not found_prod_data) and (agent_dict['PVArea'] == other_agent_dict['PVArea']) and \
                    (get_if_exists_else(agent_dict, 'PVEfficiency', default_pv_efficiency)
                     == get_if_exists_else(other_agent_dict, 'PVEfficiency', other_default_pv_eff)):
                # All parameters relating to generating solar power production are the same
                logger.debug('For agent \'{}\' found PV production data to re-use'.format(agent_dict['Name']))
                found_prod_data = True
                prod_data = mock_data[get_pv_prod_key(other_agent_dict['Name'])]
                data_to_reuse = data_to_reuse.with_column(prod_data.alias(get_pv_prod_key(agent_dict['Name'])))

            if (not found_cons_data) and (agent_dict['Name'] == other_agent_dict['Name']) and \
                    (agent_dict['GrossFloorArea'] == other_agent_dict['GrossFloorArea']) and \
                    (get_if_exists_else(agent_dict, 'FractionCommercial', 0)
                     == get_if_exists_else(other_agent_dict, 'FractionCommercial', 0)) and \
                    (get_if_exists_else(agent_dict, 'FractionSchool', 0)
                     == get_if_exists_else(other_agent_dict, 'FractionSchool', 0)):
                # All parameters relating to generating energy usage data are the same
                logger.debug('For agent \'{}\' found energy consumption data to re-use'.format(agent_dict['Name']))
                found_cons_data = True
                cons_data = mock_data.select([pl.col(get_elec_cons_key(other_agent_dict['Name'])),
                                              pl.col(get_space_heat_cons_key(other_agent_dict['Name'])),
                                              pl.col(get_hot_tap_water_cons_key(other_agent_dict['Name']))])
                data_to_reuse = pl.concat((data_to_reuse, cons_data), how='horizontal')
    return data_to_reuse


def calculate_seed_from_string(some_string: str) -> int:
    """
    Hashes the string, and truncates the value to a 32-bit integer, since that is what seeds are allowed to be.
    __hash__() is non-deterministic, so we use hashlib.
    """
    bytes_to_hash = some_string.encode('utf-8')
    hashed_hexadecimal = hashlib.sha256(bytes_to_hash).hexdigest()
    very_big_int = int(hashed_hexadecimal, 16)
    return very_big_int & 0xFFFFFFFF


if __name__ == '__main__':
    # --- Format logger for print statements
    FORMAT = "%(asctime)-15s | %(levelname)-7s | %(name)-20.20s | %(message)s"

    if not os.path.exists("../logfiles"):
        os.makedirs("../logfiles")
    file_handler = logging.FileHandler("../logfiles/generate-mock-data.log")
    stream_handler = logging.StreamHandler()

    logging.basicConfig(
        level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[file_handler, stream_handler], force=True  # Note that we remove all previously existing handlers here
    )

    # Open config file
    with open(resource_filename(DATA_PATH, CONFIG_FILE), "r") as json_file:
        config_from_file = json.load(json_file)

    run(config_from_file)
