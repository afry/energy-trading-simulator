import logging
import math
import time

import numpy as np
import pandas as pd
import json
import statsmodels.api as sm
import pickle

from statsmodels.regression.linear_model import RegressionResultsWrapper

from tradingplatformpoc.mock_data_generation_functions import load_existing_data_sets, get_all_building_agents, \
    get_elec_cons_key, get_pv_prod_key
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod

CONFIG_FILE = 'jonstaka.json'

MOCK_DATAS_PICKLE = './tradingplatformpoc/data/generated/mock_datas.pickle'

pd.options.mode.chained_assignment = None  # default='warn'

KWH_PER_YEAR_M2_ATEMP = 20  # According to Skanska: 20 kWh/year/m2 Atemp
PV_EFFICIENCY = 0.165
M2_PER_APARTMENT = 70

"""
This script generates household electricity consumption data, and rooftop PV production data, for BuildingAgents.
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
    with open('./tradingplatformpoc/data/{}'.format(CONFIG_FILE), "r") as json_file:
        config_data = json.load(json_file)

    building_agents, total_gross_floor_area = get_all_building_agents(config_data)
    building_agents_frozen_set = frozenset(building_agents)  # Need to freeze, else can't use it as key in dict
    if building_agents_frozen_set in all_data_sets:
        logger.info('Already had mock data for the configuration described in %s, exiting generate_mock_data' %
                    CONFIG_FILE)
    else:
        # So we have established that we need to generate new mock data.

        # Load model
        model = sm.load('./tradingplatformpoc/data/models/household_electricity_model.pickle')

        # Read in-data: Temperature and timestamps
        df_inputs, df_irrd = create_inputs_df('./tradingplatformpoc/data/temperature_vetelangden.csv',
                                              './tradingplatformpoc/data/varberg_irradiation_W_m2_h.csv')

        approx_n_of_apartments = math.ceil(total_gross_floor_area / M2_PER_APARTMENT)
        n_apps_done = 0

        output_per_building = pd.DataFrame({'datetime': df_inputs.index})
        output_per_building.set_index('datetime', inplace=True)

        total_time_elapsed = 0
        for agent in building_agents:
            time_elapsed, n_apps_done = simulate_and_add_to_output_df(dict(agent), df_inputs, df_irrd, model,
                                                                      output_per_building,
                                                                      n_apps_done)
            approx_n_apps_remaining = approx_n_of_apartments - n_apps_done
            total_time_elapsed = total_time_elapsed + time_elapsed
            if approx_n_apps_remaining > 0:
                time_taken_per_apartment = total_time_elapsed / n_apps_done
                estimated_time_left = approx_n_apps_remaining * time_taken_per_apartment
                logger.info('Estimated time left: {:.2f} seconds'.format(estimated_time_left))

        all_data_sets[building_agents_frozen_set] = output_per_building
        pickle.dump(all_data_sets, open(MOCK_DATAS_PICKLE, 'wb'))


def simulate_and_add_to_output_df(agent: dict, df_inputs: pd.DataFrame, df_irrd: pd.DataFrame,
                                  model: RegressionResultsWrapper, output_per_building: pd.DataFrame,
                                  n_apartments_simulated: int):
    start = time.time()
    agent = dict(agent)  # "Unfreezing" the frozenset
    logger.debug('Starting work on \'{}\''.format(agent['Name']))
    pv_area = agent['RooftopPVArea'] if "RooftopPVArea" in agent else 0
    start_seed = agent['RandomSeed'] * 1000
    df_output = simulate_for_area(df_inputs, model, agent['GrossFloorArea'], start_seed)
    output_per_building[get_elec_cons_key(agent['Name'])] = df_output.sum(axis=1)
    output_per_building[get_pv_prod_key(agent['Name'])] = calculate_solar_prod(df_irrd['irradiation'], pv_area,
                                                                               PV_EFFICIENCY)
    n_apartments_simulated = n_apartments_simulated + len(df_output.columns)
    end = time.time()
    time_elapsed = end - start
    logger.debug('Finished work on \'{}\', took {:.2f} seconds'.format(agent['Name'], time_elapsed))
    return time_elapsed, n_apartments_simulated


def simulate_for_area(df_inputs: pd.DataFrame, model: RegressionResultsWrapper, gross_floor_area: float,
                      start_seed: int):
    df_output = pd.DataFrame({'datetime': df_inputs.index})
    df_output.set_index('datetime', inplace=True)

    n_apartments = math.ceil(gross_floor_area / M2_PER_APARTMENT)
    logger.debug('Number of apartments: {:d}'.format(n_apartments))

    for i in range(0, n_apartments):
        unscaled_simulated_values_for_apartment = simulate_series(df_inputs, start_seed + i, model)
        # Scale
        m2_for_this_apartment = M2_PER_APARTMENT if i < (n_apartments - 1) else \
            (gross_floor_area - M2_PER_APARTMENT * (n_apartments - 1))
        simulated_values_for_this_apartment = scale_electricity_consumption(unscaled_simulated_values_for_apartment,
                                                                            m2_for_this_apartment)
        df_output['apartment' + str(i)] = simulated_values_for_this_apartment
    return df_output


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
        model.params['np.where(np.isnan(energy_prev), 0, np.minimum(energy_prev, 0.7))'] * np.minimum(energy_prev, 0.7)


def create_inputs_df(temperature_csv_path: str, irradiation_csv_path: str):
    """
    Create a pd.DataFrame with certain columns that are needed to predict from the household electricity linear model.
    @param temperature_csv_path: Path to a CSV-file with datetime-stamps and temperature readings, in degrees C.
    @param irradiation_csv_path: Path to a CSV-file with datetime-stamps and solar irradiance readings, in W/m2.
    @return: A pd.DataFrame
    """
    df_temp = pd.read_csv(temperature_csv_path, names=['datetime', 'temperature'],
                          delimiter=';', header=0)
    df_temp['datetime'] = pd.to_datetime(df_temp['datetime'])
    df_irrd = pd.read_csv(irradiation_csv_path)
    df_irrd['datetime'] = pd.to_datetime(df_irrd['datetime'])

    df_inputs = df_temp.merge(df_irrd)
    df_inputs = df_inputs.interpolate(method='linear')  # In case there are any missing values
    df_inputs['hour_of_day'] = df_inputs['datetime'].dt.hour + 1
    df_inputs['day_of_week'] = df_inputs['datetime'].dt.dayofweek + 1
    df_inputs['day_of_month'] = df_inputs['datetime'].dt.day
    df_inputs['month_of_year'] = df_inputs['datetime'].dt.month
    df_inputs.set_index('datetime', inplace=True)
    df_inputs['major_holiday'] = is_major_holiday_sweden(df_inputs['month_of_year'], df_inputs['day_of_month'])
    df_inputs['pre_major_holiday'] = is_day_before_major_holiday_sweden(df_inputs['month_of_year'],
                                                                        df_inputs['day_of_month'])

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


def scale_electricity_consumption(unscaled_simulated_values_for_year: pd.Series, m2: float):
    current_yearly_sum = unscaled_simulated_values_for_year.sum()
    wanted_yearly_sum = m2 * KWH_PER_YEAR_M2_ATEMP
    return unscaled_simulated_values_for_year * (wanted_yearly_sum / current_yearly_sum)


if __name__ == '__main__':
    main()
