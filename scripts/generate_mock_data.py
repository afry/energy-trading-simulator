import json
import logging
import math
import pickle
import time
from typing import Tuple

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

import statsmodels.api as sm
from statsmodels.regression.linear_model import RegressionResultsWrapper

from tradingplatformpoc import commercial_heating_model
from tradingplatformpoc.mock_data_generation_functions import get_all_residential_building_agents, \
    get_commercial_electricity_consumption_hourly_factor, \
    get_commercial_heating_consumption_hourly_factor, \
    get_elec_cons_key, get_heat_cons_key, get_pv_prod_key, \
    get_school_heating_consumption_hourly_factor, \
    load_existing_data_sets
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod

CONFIG_FILE = 'jonstaka.json'

DATA_PATH = 'tradingplatformpoc.data'

MOCK_DATAS_PICKLE = resource_filename(DATA_PATH, 'mock_datas.pickle')

pd.options.mode.chained_assignment = None  # default='warn'

KWH_PER_YEAR_M2_ATEMP = 20  # According to Skanska: 20 kWh/year/m2 Atemp
PV_EFFICIENCY = 0.165
M2_PER_APARTMENT = 70
# Will use this to set random seed. Agent with start_seed = 1 will have seed 1 for household electricity, and
# RESIDENTIAL_HEATING_SEED_OFFSET+1 for residential heating, and COMMERCIAL_SEED_OFFSET+1 for commercial electricity...
RESIDENTIAL_HEATING_SEED_OFFSET = 1000
EVERY_X_HOURS = 3  # Random noise will be piecewise linear, with knots every X hours
HEATING_RELATIVE_ERROR_STD_DEV = 0.2
KWH_PER_YEAR_M2_RESIDENTIAL_HEATING = 43.75  # See https://doc.afdrift.se/display/RPJ/BDAB+data
# Constants for the 'commercial' electricity bit:
COMMERCIAL_ELECTRICITY_SEED_OFFSET = 100000
KWH_ELECTRICITY_PER_YEAR_M2_COMMERCIAL = 118
COMMERCIAL_ELECTRICITY_RELATIVE_ERROR_STD_DEV = 0.2
# Constants for the 'commercial' heating bit:
COMMERCIAL_HEATING_SEED_OFFSET = 10000000
SCHOOL_HEATING_SEED_OFFSET = 100000000
# As per https://doc.afdrift.se/display/RPJ/Commercial+areas
KWH_SPACE_HEATING_PER_YEAR_M2_COMMERCIAL = 32
KWH_HOT_TAP_WATER_PER_YEAR_M2_COMMERCIAL = 3.5
COMMERCIAL_HOT_TAP_WATER_RELATIVE_ERROR_STD_DEV = 0.2
# Constants for school
SCHOOL_ELECTRICITY_SEED_OFFSET = 1000000000
KWH_ELECTRICITY_PER_YEAR_M2_SCHOOL = 90
SCHOOL_ELECTRICITY_RELATIVE_ERROR_STD_DEV = 0.2
SCHOOL_HOT_TAP_WATER_RELATIVE_ERROR_STD_DEV = 0.2
KWH_HOT_TAP_WATER_PER_YEAR_M2_SCHOOL = 7
KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL = 25

"""
This script generates the following, for ResidentialBuildingAgents:
*Household electricity consumption data
*Commercial electricity consumption data
*Residential heating consumption data
*Commercial heating consumption data
*Rooftop PV production data
It stores such data in the MOCK_DATAS_PICKLE file, as a dictionary, where the set of BuildingAgents used to generate the
data is the key, and a pd.DataFrame of generated data is the value. This way, simulation_runner can get the correct mock
data set for the given config.
For some more information: https://doc.afdrift.se/display/RPJ/Household+electricity+mock-up
"""

# --- Format logger for print statements
FORMAT = "%(asctime)-15s | %(levelname)-7s | %(name)-20.20s | %(message)s"

file_handler = logging.FileHandler("../generate-mock-data.log")
stream_handler = logging.StreamHandler()

logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[file_handler, stream_handler]
)

logger = logging.getLogger(__name__)


def main():
    # Load pre-existing mock data sets
    all_data_sets = load_existing_data_sets(MOCK_DATAS_PICKLE)

    # Open config file
    with open(resource_filename(DATA_PATH, CONFIG_FILE), "r") as json_file:
        config_data = json.load(json_file)

    residential_building_agents, total_gross_floor_area_residential = get_all_residential_building_agents(config_data)

    # Need to freeze, else can't use it as key in dict
    residential_building_agents_frozen_set = frozenset(residential_building_agents)

    if residential_building_agents_frozen_set in all_data_sets:
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
        output_per_building = pd.DataFrame({'datetime': df_inputs.index})
        output_per_building.set_index('datetime', inplace=True)
        logger.debug('Output dataframes created')

        total_time_elapsed = 0
        n_areas_done = 0
        n_areas = len(residential_building_agents)
        logger.debug('{} areas to iterate over'.format(n_areas))
        for agent in residential_building_agents:
            logger.debug('Entered agent loop')
            time_elapsed = simulate_and_add_to_output_df(dict(agent), df_inputs, df_irrd, model, output_per_building)
            n_areas_done = n_areas_done + 1
            n_areas_remaining = n_areas - n_areas_done
            total_time_elapsed = total_time_elapsed + time_elapsed
            if n_areas_remaining > 0:
                time_taken_per_area = total_time_elapsed / n_areas_done
                estimated_time_left = n_areas_remaining * time_taken_per_area
                logger.info('Estimated time left: {:.2f} seconds'.format(estimated_time_left))

        all_data_sets[residential_building_agents_frozen_set] = output_per_building
        pickle.dump(all_data_sets, open(MOCK_DATAS_PICKLE, 'wb'))


def simulate_and_add_to_output_df(agent: dict, df_inputs: pd.DataFrame, df_irrd: pd.DataFrame,
                                  model: RegressionResultsWrapper, output_per_actor: pd.DataFrame):
    start = time.time()
    agent = dict(agent)  # "Unfreezing" the frozenset
    logger.debug('Starting work on \'{}\''.format(agent['Name']))
    pv_area = agent['RooftopPVArea'] if "RooftopPVArea" in agent else 0

    seed_residential_electricity = agent['RandomSeed']
    seed_residential_heating = agent['RandomSeed'] + RESIDENTIAL_HEATING_SEED_OFFSET
    seed_commercial_electricity = agent['RandomSeed'] + COMMERCIAL_ELECTRICITY_SEED_OFFSET
    seed_commercial_heating = agent['RandomSeed'] + COMMERCIAL_HEATING_SEED_OFFSET
    seed_school_electricity = agent["RandomSeed"] + SCHOOL_ELECTRICITY_SEED_OFFSET
    seed_school_heating = agent["RandomSeed"] + SCHOOL_HEATING_SEED_OFFSET
    fraction_commercial = agent['FractionCommercial'] if 'FractionCommercial' in agent else 0.0
    fraction_school = agent['FractionSchool'] if 'FractionSchool' in agent else 0.0
    logger.debug("Total non-residential fraction {}".format(fraction_commercial + fraction_school))
    if fraction_school + fraction_commercial > 1:
        logger.error("Total non-residential fractions for agent {} larger than 100%".format(agent["Name"]))
        exit(1)
    fraction_residential = 1.0 - fraction_commercial - fraction_school
    commercial_gross_floor_area = agent['GrossFloorArea'] * fraction_commercial
    residential_gross_floor_area = agent['GrossFloorArea'] * fraction_residential
    school_gross_floor_area_m2 = agent['GrossFloorArea'] * fraction_school

    commercial_electricity_cons = simulate_commercial_area_electricity(commercial_gross_floor_area,
                                                                       seed_commercial_electricity, df_inputs.index,
                                                                       KWH_ELECTRICITY_PER_YEAR_M2_COMMERCIAL,
                                                                       COMMERCIAL_ELECTRICITY_RELATIVE_ERROR_STD_DEV)
    commercial_heating_cons = simulate_commercial_area_total_heating(commercial_gross_floor_area,
                                                                     seed_commercial_heating, df_inputs)

    residential_heating_cons = simulate_residential_total_heating(df_inputs, residential_gross_floor_area,
                                                                  seed_residential_heating)

    household_electricity_cons = simulate_household_electricity_aggregated(
        df_inputs, model, residential_gross_floor_area, seed_residential_electricity)

    school_electricity_cons = simulate_commercial_area_electricity(school_gross_floor_area_m2, seed_school_electricity,
                                                                   df_inputs.index, KWH_ELECTRICITY_PER_YEAR_M2_SCHOOL,
                                                                   SCHOOL_ELECTRICITY_RELATIVE_ERROR_STD_DEV)
    school_heating_cons = simulate_school_area_total_heating(school_gross_floor_area_m2, seed_school_heating,
                                                             df_inputs)
    print("Adding output for agent {}", agent['Name'])
    output_per_actor[get_elec_cons_key(agent['Name'])] = household_electricity_cons + commercial_electricity_cons + \
        school_electricity_cons
    output_per_actor[get_heat_cons_key(agent['Name'])] = residential_heating_cons + commercial_heating_cons + \
        school_heating_cons

    output_per_actor[get_pv_prod_key(agent['Name'])] = calculate_solar_prod(df_irrd['irradiation'], pv_area,
                                                                            PV_EFFICIENCY)
    end = time.time()
    time_elapsed = end - start
    logger.debug('Finished work on \'{}\', took {:.2f} seconds'.format(agent['Name'], time_elapsed))
    return time_elapsed


def simulate_household_electricity_by_apartment(df_inputs: pd.DataFrame, model: RegressionResultsWrapper,
                                                gross_floor_area_m2: float, start_seed: int) -> Tuple[pd.Series, int]:
    """
    --- DEPRECATED: Use simulate_household_electricity_aggregated ---
    Simulates the aggregated household electricity consumption for an area. Calculates a rough number of apartments/
    dwellings, and simulates the household electricity on an individual basis (since the model we have is for individual
    dwellings, not whole buildings aggregated) and then sums over these.
    Returns a Series with the data, as well as an integer with the number of apartments that was used.
    """
    df_output = pd.DataFrame({'datetime': df_inputs.index})
    df_output.set_index('datetime', inplace=True)

    n_apartments = math.ceil(gross_floor_area_m2 / M2_PER_APARTMENT)
    logger.debug('Number of apartments in area: {:d}'.format(n_apartments))

    for i in range(0, n_apartments):
        unscaled_simulated_values_for_apartment = simulate_series(df_inputs, start_seed + i, model)
        # Scale
        m2_for_this_apartment = M2_PER_APARTMENT if i < (n_apartments - 1) else \
            (gross_floor_area_m2 - M2_PER_APARTMENT * (n_apartments - 1))
        simulated_values_for_this_apartment = scale_energy_consumption(unscaled_simulated_values_for_apartment,
                                                                       m2_for_this_apartment,
                                                                       KWH_PER_YEAR_M2_ATEMP)
        df_output['apartment' + str(i)] = simulated_values_for_this_apartment
    return df_output.sum(axis=1), n_apartments


def simulate_household_electricity_aggregated(df_inputs: pd.DataFrame, model: RegressionResultsWrapper,
                                              gross_floor_area_m2: float, start_seed: int) -> pd.Series:
    """
    Simulates the aggregated household electricity consumption for an area. Instead of simulating individual apartments,
    this method just sees the whole area as one apartment, and simulates that. This drastically reduces runtime.
    Mathematically, the sum of log-normal random variables is approximately log-normal, which supports this way of doing
    things. Furthermore, just simulating one series instead of ~100 (or however many apartments are in an area), should
    increase randomness. This is probably not a bad thing for us: Since our simulations stem from a model fit on one
    single apartment, increased randomness could actually be said to make a lot of sense.
    Returns a pd.Series with the data.
    """
    df_output = pd.DataFrame({'datetime': df_inputs.index})
    df_output.set_index('datetime', inplace=True)

    unscaled_simulated_values_for_area = simulate_series(df_inputs, start_seed, model)
    # Scale
    simulated_values_for_this_area = scale_energy_consumption(unscaled_simulated_values_for_area,
                                                              gross_floor_area_m2,
                                                              KWH_PER_YEAR_M2_ATEMP)
    return simulated_values_for_this_area


def simulate_series(input_df: pd.DataFrame, rand_seed: int, model: RegressionResultsWrapper):
    """
    Runs simulations using "model" and "input_df", with "rand_seed" as the random seed (can be specified, so that the
    experiment becomes reproducible, and also when simulating several different apartments/houses, the simulations don't
    end up identical).
    The fact that autoregressive parts are included in the model, makes it more difficult to predict with, we can't just
    use the predict-method. As explained in https://doc.afdrift.se/display/RPJ/Household+electricity+mock-up,
    we use the predict-method first and then add on autoregressive terms afterwards. The autoregressive parts are
    calculated in calculate_adjustment_for_energy_prev(...).
    :param input_df: pd.DataFrame
    :param rand_seed: int
    :param model: statsmodels.regression.linear_model.RegressionResultsWrapper
    :return: pd.Series
    """
    np.random.seed(rand_seed)  # set random seed
    input_df['energy_prev'] = 0
    input_df['energy_prev'].iloc[0] = np.nan

    input_df['z_hat'] = model.predict(input_df)  # run regression with other_prev = 0, using the other_prev_start_dummy
    std_dev = np.sqrt(model.scale)  # store standard error
    input_df['simulated_log_energy_unscaled'] = np.nan  # y_t

    eps_vec = np.random.normal(0, std_dev, size=input_df.shape[0])

    # For t=0, z=y
    input_df['simulated_log_energy_unscaled'].iloc[0] = input_df['z_hat'].iloc[0] + eps_vec[0]

    # For t>0, y_t = max(0, zhat_t + beta * y_(t-1) + eps_t)
    for t in range(1, len(input_df)):
        energy_prev = np.exp(input_df['simulated_log_energy_unscaled'].iloc[t - 1])
        adjustment_for_prev = calculate_adjustment_for_energy_prev(model, energy_prev)
        input_df['simulated_log_energy_unscaled'].iloc[t] = input_df['z_hat'].iloc[t] + adjustment_for_prev + eps_vec[t]
    return np.exp(input_df['simulated_log_energy_unscaled'])


def calculate_adjustment_for_energy_prev(model: RegressionResultsWrapper, energy_prev: float):
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
        Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create a pd.DataFrame with certain columns that are needed to predict from the household electricity linear model.
    @param temperature_csv_path: Path to a CSV-file with datetime-stamps and temperature readings, in degrees C.
    @param irradiation_csv_path: Path to a CSV-file with datetime-stamps and solar irradiance readings, in W/m2.
    @param heating_csv_path: Path to a CSV-file with datetime-stamps and heating energy readings, in kW.
    @return: Two pd.DataFrames:
        The first one contains date/time-related columns, as well as outdoor temperature readings and heating energy
            demand data from Vetelangden. This dataframe will be used to simulate electricity and heat demands.
        The second one contains irradiation data, which is used to estimate PV production.
    """
    df_temp = pd.read_csv(temperature_csv_path, names=['datetime', 'temperature'],
                          delimiter=';', header=0)
    df_temp['datetime'] = pd.to_datetime(df_temp['datetime'])
    df_irrd = pd.read_csv(irradiation_csv_path)
    df_irrd['datetime'] = pd.to_datetime(df_irrd['datetime'])

    df_inputs = df_temp.merge(df_irrd)
    # In case there are any missing values
    df_inputs[['temperature', 'irradiation']] = df_inputs[['temperature', 'irradiation']].interpolate(method='linear')
    df_inputs['hour_of_day'] = df_inputs['datetime'].dt.hour + 1
    df_inputs['day_of_week'] = df_inputs['datetime'].dt.dayofweek + 1
    df_inputs['day_of_month'] = df_inputs['datetime'].dt.day
    df_inputs['month_of_year'] = df_inputs['datetime'].dt.month
    df_inputs.set_index('datetime', inplace=True)
    df_inputs['major_holiday'] = is_major_holiday_sweden(df_inputs['month_of_year'], df_inputs['day_of_month'])
    df_inputs['pre_major_holiday'] = is_day_before_major_holiday_sweden(df_inputs['month_of_year'],
                                                                        df_inputs['day_of_month'])

    df_heat = pd.read_csv(heating_csv_path, names=['datetime', 'rad_energy', 'hw_energy'], header=0)
    df_heat['heating_energy_kwh'] = df_heat['rad_energy'] + df_heat['hw_energy']
    df_heat.drop(['rad_energy', 'hw_energy'], axis=1, inplace=True)
    df_heat['datetime'] = pd.to_datetime(df_heat['datetime'])
    df_heat.set_index('datetime', inplace=True)

    df_inputs = df_inputs.merge(df_heat, left_index=True, right_index=True)

    df_irrd.set_index('datetime', inplace=True)
    return df_inputs, df_irrd


def is_major_holiday_sweden(month_of_year: int, day_of_month: int):
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


def is_day_before_major_holiday_sweden(month_of_year: int, day_of_month: int):
    # Major holidays will naturally have a big impact on household electricity usage patterns, with people not working
    # etc. Included here are:
    # Day before christmas eve, New years eve, day before epiphany, Valborg, day before national day.
    return ((month_of_year == 12) & (day_of_month == 23)) | \
           ((month_of_year == 12) & (day_of_month == 31)) | \
           ((month_of_year == 1) & (day_of_month == 5)) | \
           ((month_of_year == 4) & (day_of_month == 30)) | \
           ((month_of_year == 6) & (day_of_month == 5))


def scale_energy_consumption(unscaled_simulated_values_kwh: pd.Series, m2: float, kwh_per_year_per_m2: float):
    # unscaled_simulated_values may contain more than 1 year, so just look at the first 8766 hours (365.25 days)
    current_yearly_sum = unscaled_simulated_values_kwh.iloc[:8766].sum()
    wanted_yearly_sum = m2 * kwh_per_year_per_m2
    return unscaled_simulated_values_kwh * (wanted_yearly_sum / current_yearly_sum)


def simulate_commercial_area_electricity(commercial_gross_floor_area_m2: float, random_seed: int,
                                         datetimes: pd.DatetimeIndex, kwh_elec_per_yr_per_m2: float, elec_rel_err_stdev:
                                         float) -> pd.Series:
    """
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas
    @return A pd.Series with hourly electricity consumption, in kWh.
    """
    factors = [get_commercial_electricity_consumption_hourly_factor(x) for x in datetimes.hour]
    np.random.seed(random_seed)
    relative_errors = np.random.normal(0, elec_rel_err_stdev, len(factors))
    unscaled_values = factors * (1 + relative_errors)
    unscaled_series = pd.Series(unscaled_values, index=datetimes)
    scaled_series = scale_energy_consumption(unscaled_series, commercial_gross_floor_area_m2,
                                             kwh_elec_per_yr_per_m2)
    return scaled_series


def simulate_commercial_area_total_heating(commercial_gross_floor_area_m2: float, random_seed: int,
                                           input_df: pd.DataFrame) -> pd.Series:
    """
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas and
    https://doc.afdrift.se/display/RPJ/Coop+heating+energy+use+mock-up
    Total heating = space heating + hot water
    @return A pd.Series with hourly total heating load, in kWh.
    """
    space_heating = simulate_commercial_area_space_heating(commercial_gross_floor_area_m2, random_seed, input_df)
    hot_tap_water = simulate_commercial_area_hot_tap_water(commercial_gross_floor_area_m2, random_seed, input_df.index)
    return space_heating + hot_tap_water


def simulate_commercial_area_hot_tap_water(commercial_gross_floor_area_m2: float, random_seed: int,
                                           datetimes: pd.DatetimeIndex) -> pd.Series:
    """
    Gets a factor based on the hour of day, multiplies it by a noise-factor, and scales it.
    @return A pd.Series with hot tap water load for the area, scaled to KWH_SPACE_HEATING_PER_YEAR_M2_COMMERCIAL.
    """
    time_factors = [get_commercial_heating_consumption_hourly_factor(x) for x in datetimes.hour]
    np.random.seed(random_seed)
    relative_errors = np.random.normal(0, COMMERCIAL_HOT_TAP_WATER_RELATIVE_ERROR_STD_DEV, len(time_factors))
    unscaled_values = time_factors * (1 + relative_errors)
    unscaled_series = pd.Series(unscaled_values, index=datetimes)
    scaled_series = scale_energy_consumption(unscaled_series, commercial_gross_floor_area_m2,
                                             KWH_HOT_TAP_WATER_PER_YEAR_M2_COMMERCIAL)
    return scaled_series


def simulate_commercial_area_space_heating(commercial_gross_floor_area_m2: float, random_seed: int,
                                           input_df: pd.DataFrame) -> pd.Series:
    """
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas and
    https://doc.afdrift.se/display/RPJ/Coop+heating+energy+use+mock-up
    @return A pd.Series with space heating load for the area, scaled to KWH_SPACE_HEATING_PER_YEAR_M2_COMMERCIAL.
    """
    np.random.seed(random_seed)
    # Probability that there is 0 heating demand:
    predicted_prob_of_0 = input_df['temperature'].\
        apply(lambda x: commercial_heating_model.probability_of_0_space_heating(x))
    # Simulate whether there is 0 heating demand:
    has_heat_demand = np.random.binomial(n=1, p=1 - predicted_prob_of_0)  # 1 if heat demand > 0

    # Now, if heat demand non-zero, how much is it?
    pred_given_non_0 = input_df['temperature'].\
        apply(lambda x: commercial_heating_model.space_heating_given_more_than_0(x))
    # Simulate
    heat_given_non_0 = np.maximum(0, np.random.normal(loc=pred_given_non_0, scale=commercial_heating_model.LM_STD_DEV))

    # Combine the above
    sim_energy_unscaled = np.where(has_heat_demand == 0, 0, heat_given_non_0)

    # Adjust for opening times
    datetimes = input_df.index
    time_factors = [get_commercial_heating_consumption_hourly_factor(x) for x in datetimes.hour]
    sim_energy_unscaled = sim_energy_unscaled * time_factors

    # Scale
    scaled_series = scale_energy_consumption(pd.Series(sim_energy_unscaled, index=datetimes),
                                             commercial_gross_floor_area_m2, KWH_SPACE_HEATING_PER_YEAR_M2_COMMERCIAL)

    return scaled_series


def simulate_school_area_total_heating(school_gross_floor_area_m2: float, random_seed: int,
                                       input_df: pd.DataFrame) -> pd.Series:
    """
    This function follows the recipe outlined in the corresponding function for commercial buildings.
    Total energy demand ("load function") = space heating + hot water
    @return A pd.Series with hourly total heating load, in kWh.
    """
    space_heating = simulate_school_area_space_heating(school_gross_floor_area_m2, random_seed, input_df)
    hot_tap_water = simulate_school_area_hot_tap_water(school_gross_floor_area_m2, random_seed, input_df.index)
    return space_heating + hot_tap_water


def simulate_school_area_hot_tap_water(school_gross_floor_area_m2: float, random_seed: int,
                                       datetimes: pd.DatetimeIndex) -> pd.Series:
    """
    Gets a factor based on the hour of day, multiplies it by a noise-factor, and scales it.
    @return A pd.Series with hot tap water load for the area, scaled to KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL.
    """
    time_factors = [get_school_heating_consumption_hourly_factor(x) for x in datetimes]
    np.random.seed(random_seed)
    relative_errors = np.random.normal(0, SCHOOL_HOT_TAP_WATER_RELATIVE_ERROR_STD_DEV, len(time_factors))
    unscaled_values = time_factors * (1 + relative_errors)
    unscaled_series = pd.Series(unscaled_values, index=datetimes)
    scaled_series = scale_energy_consumption(unscaled_series, school_gross_floor_area_m2,
                                             KWH_HOT_TAP_WATER_PER_YEAR_M2_SCHOOL)
    return scaled_series


def simulate_school_area_space_heating(school_gross_floor_area_m2: float, random_seed: int,
                                       input_df: pd.DataFrame) -> pd.Series:
    """
    For more information, see https://doc.afdrift.se/display/RPJ/Commercial+areas and
    https://doc.afdrift.se/display/RPJ/Coop+heating+energy+use+mock-up
    @return A pd.Series with space heating load for the area, scaled to KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL.
    """
    # TODO: simulate_school_area_space_heating and simulate_commercial_area_space_heating could be generified, if we
    #  extract the get_school_heating_consumption_hourly_factor function and the KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL
    #  constant to parameters.
    np.random.seed(random_seed)

    # Probability that there is 0 heating demand:
    predicted_prob_of_0 = input_df['temperature'].\
        apply(lambda x: commercial_heating_model.probability_of_0_space_heating(x))
    # Simulate whether there is 0 heating demand:
    has_heat_demand = np.random.binomial(n=1, p=1 - predicted_prob_of_0)  # 1 if heat demand > 0

    # Now, if heat demand non-zero, how much is it?
    pred_given_non_0 = input_df['temperature'].\
        apply(lambda x: commercial_heating_model.space_heating_given_more_than_0(x))
    # Simulate
    heat_given_non_0 = np.maximum(0, np.random.normal(loc=pred_given_non_0, scale=commercial_heating_model.LM_STD_DEV))

    # Combine the above
    sim_energy_unscaled = np.where(has_heat_demand == 0, 0, heat_given_non_0)

    # Adjust for opening times
    datetimes = input_df.index
    time_factors = [get_school_heating_consumption_hourly_factor(x) for x in datetimes]
    sim_energy_unscaled = sim_energy_unscaled * time_factors

    # Scale
    scaled_series = scale_energy_consumption(pd.Series(sim_energy_unscaled, index=datetimes),
                                             school_gross_floor_area_m2, KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL)

    return scaled_series


def simulate_residential_total_heating(df_inputs: pd.DataFrame, gross_floor_area_m2: float, random_seed: int) -> \
        pd.Series:
    """
    Following along with https://doc.afdrift.se/display/RPJ/Jonstaka+heating+mock-up
    But as for electricity, we'll just see the whole sub-area as 1 house, shouldn't matter too much.
    Total heating meaning space heating and hot tap water combined.
    df_inputs needs to contain a 'heating_energy_kwh' column, with the Vetelangden data.
    Returns a pd.Series with simulated data.
    """

    nrow_input_df = len(df_inputs.index)
    every_xth = np.arange(0, nrow_input_df, EVERY_X_HOURS)
    points_to_generate = len(every_xth)

    np.random.seed(random_seed)
    generated_points = np.random.normal(1, HEATING_RELATIVE_ERROR_STD_DEV, points_to_generate)

    noise = np.empty((nrow_input_df,))
    noise[:] = np.nan
    noise[every_xth] = generated_points

    nans, x = nan_helper(noise)
    noise[nans] = np.interp(x(nans), x(~nans), noise[~nans])

    vetelangden_data = df_inputs['heating_energy_kwh']
    heating_unscaled = noise * vetelangden_data
    # Scale using BDAB's estimate
    heating_scaled = scale_energy_consumption(heating_unscaled, gross_floor_area_m2,
                                              KWH_PER_YEAR_M2_RESIDENTIAL_HEATING)
    return heating_scaled


def nan_helper(y):
    """Helper to handle indices and logical indices of NaNs.

    Input:
        - y, 1d numpy array with possible NaNs
    Output:
        - nans, logical indices of NaNs
        - index, a function, with signature indices= index(logical_indices),
          to convert logical indices of NaNs to 'equivalent' indices
    Example:
        >>> # linear interpolation of NaNs
        >>> y = np.array([1.0, np.nan, 2.0])
        >>> nans, x= nan_helper(y)
        >>> y[nans]= np.interp(x(nans), x(~nans), y[~nans])
    """

    return np.isnan(y), lambda z: z.nonzero()[0]


if __name__ == '__main__':
    main()
