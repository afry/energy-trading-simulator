import hashlib
import logging
import os
import pickle
import time
from typing import Any, Dict, Iterable, Tuple

from pkg_resources import resource_filename

import polars as pl

from statsmodels.regression.linear_model import RegressionResultsWrapper

from tradingplatformpoc.compress import bz2_decompress_pickle
from tradingplatformpoc.config.access_config import read_config
from tradingplatformpoc.data.preproccessing import create_inputs_df_for_mock_data_generation, read_heating_data, \
    read_irradiation_data, read_temperature_data
from tradingplatformpoc.generate_data.generation_functions.common import add_datetime_value_frames
from tradingplatformpoc.generate_data.generation_functions.non_residential.commercial import \
    get_commercial_electricity_consumption_hourly_factor, \
    simulate_commercial_area_total_heating
from tradingplatformpoc.generate_data.generation_functions.non_residential.common import simulate_area_electricity
from tradingplatformpoc.generate_data.generation_functions.non_residential.school import \
    get_school_heating_consumption_hourly_factor, simulate_school_area_heating
from tradingplatformpoc.generate_data.generation_functions.residential.residential import \
    simulate_household_electricity_aggregated, simulate_residential_total_heating
from tradingplatformpoc.generate_data.mock_data_generation_functions import MockDataKey, get_all_building_agents, \
    get_elec_cons_key, get_hot_tap_water_cons_key, get_space_heat_cons_key, load_existing_data_sets
from tradingplatformpoc.trading_platform_utils import get_if_exists_else

DATA_PATH = 'tradingplatformpoc.data'

MOCK_DATAS_PICKLE = resource_filename(DATA_PATH, 'mock_datas.pickle')

# Will use these to set random seed.
RESIDENTIAL_HEATING_SEED_SUFFIX = "RH"
COMMERCIAL_ELECTRICITY_SEED_SUFFIX = "CE"
COMMERCIAL_HEATING_SEED_SUFFIX = "CH"
SCHOOL_HEATING_SEED_SUFFIX = "SH"
SCHOOL_ELECTRICITY_SEED_SUFFIX = "SE"

"""
This script generates the following, for BuildingAgents:
*Household electricity consumption data
*Commercial electricity consumption data
*Residential hot water consumption data
*Commercial hot water consumption data
*Residential space heating consumption data
*Commercial space heating consumption data
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
    mock_data_key = MockDataKey(frozenset(building_agents), frozenset(config_data['MockDataConstants'].items()))

    if mock_data_key in all_data_sets:
        logger.info('Already had mock data for the default configuration described in, exiting generate_mock_data')
    else:
        # So we have established that we need to generate new mock data.
        logger.debug('Beginning mock data generation')
        # Load model
        model = bz2_decompress_pickle(resource_filename(DATA_PATH, 'models/household_electricity_model.pbz2'))
        logger.debug('Model loaded')

        # Read in-data: Temperature and timestamps
        df_inputs = create_inputs_df_for_mock_data_generation(
            read_temperature_data(),
            read_irradiation_data(),
            read_heating_data()
        )

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
            output_per_building, time_elapsed = simulate_and_add_to_output_df(config_data, agent_dict, lazy_inputs,
                                                                              n_rows, model, output_per_building,
                                                                              all_data_sets)
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


def simulate_and_add_to_output_df(config_data: Dict[str, Any], agent: dict, df_inputs: pl.LazyFrame, n_rows: int,
                                  model: RegressionResultsWrapper, output_per_actor: pl.DataFrame,
                                  all_data_sets: dict) -> Tuple[pl.DataFrame, float]:
    start = time.time()
    agent = dict(agent)  # "Unfreezing" the frozenset
    logger.debug('Starting work on \'{}\''.format(agent['Name']))

    pre_existing_data = find_agent_in_other_data_sets(agent, config_data['MockDataConstants'], all_data_sets)
    if len(pre_existing_data.columns) > 0:
        output_per_actor = output_per_actor.join(pre_existing_data, on='datetime', how='left')

    if (not get_elec_cons_key(agent['Name']) in output_per_actor.columns) or \
            (not get_space_heat_cons_key(agent['Name']) in output_per_actor.columns) or \
            (not get_hot_tap_water_cons_key(agent['Name']) in output_per_actor.columns):
        
        # Seeds
        seed_residential_electricity = calculate_seed_from_string(agent['Name'])
        seed_residential_heating = calculate_seed_from_string(agent['Name'] + RESIDENTIAL_HEATING_SEED_SUFFIX)
        seed_commercial_electricity = calculate_seed_from_string(agent['Name'] + COMMERCIAL_ELECTRICITY_SEED_SUFFIX)
        seed_commercial_heating = calculate_seed_from_string(agent['Name'] + COMMERCIAL_HEATING_SEED_SUFFIX)
        seed_school_electricity = calculate_seed_from_string(agent['Name'] + SCHOOL_ELECTRICITY_SEED_SUFFIX)
        seed_school_heating = calculate_seed_from_string(agent['Name'] + SCHOOL_HEATING_SEED_SUFFIX)

        # Fraction of GrossFloorArea in commercial, school and residential
        fraction_commercial = get_if_exists_else(agent, 'FractionCommercial', 0)
        fraction_school = get_if_exists_else(agent, 'FractionSchool', 0)
        logger.debug("Total non-residential fraction {}".format(fraction_commercial + fraction_school))
        if fraction_school + fraction_commercial > 1:
            logger.error("Total non-residential fractions for agent {} larger than 100%".format(agent["Name"]))
            exit(1)
        fraction_residential = 1.0 - fraction_commercial - fraction_school

        # COMMERCIAL
        commercial_gross_floor_area = agent['GrossFloorArea'] * fraction_commercial

        commercial_electricity_cons = simulate_area_electricity(
            agent['GrossFloorArea'] * fraction_commercial,
            seed_commercial_electricity,
            df_inputs,
            config_data['MockDataConstants']['CommercialElecKwhPerYearM2'],
            config_data['MockDataConstants']['CommercialElecRelativeErrorStdDev'],
            get_commercial_electricity_consumption_hourly_factor,
            n_rows)
        
        commercial_space_heating_cons, commercial_hot_tap_water_cons = simulate_commercial_area_total_heating(
            config_data,
            commercial_gross_floor_area,
            seed_commercial_heating,
            df_inputs,
            n_rows)
        
        # SCHOOL
        school_gross_floor_area_m2 = agent['GrossFloorArea'] * fraction_school

        school_electricity_cons = simulate_area_electricity(
            school_gross_floor_area_m2,
            seed_school_electricity,
            df_inputs,
            config_data['MockDataConstants']['SchoolElecKwhPerYearM2'],
            config_data['MockDataConstants']['SchoolElecRelativeErrorStdDev'],
            get_school_heating_consumption_hourly_factor,
            n_rows)

        school_space_heating_cons, school_hot_tap_water_cons = simulate_school_area_heating(
            config_data,
            school_gross_floor_area_m2,
            seed_school_heating,
            df_inputs,
            n_rows)

        # RESIDENTIAL
        residential_gross_floor_area = agent['GrossFloorArea'] * fraction_residential

        household_electricity_cons = simulate_household_electricity_aggregated(
            df_inputs,
            model,
            residential_gross_floor_area,
            seed_residential_electricity,
            n_rows,
            config_data['MockDataConstants']['ResidentialElecKwhPerYearM2Atemp'])

        residential_space_heating_cons, residential_hot_tap_water_cons = simulate_residential_total_heating(
            config_data,
            df_inputs,
            n_rows,
            residential_gross_floor_area,
            seed_residential_heating)

        logger.debug("Adding output for agent {}".format(agent['Name']))
        # Note: Here we join a normal DataFrame (output_per_actor) with LazyFrames
        output_per_actor = output_per_actor. \
            join(add_datetime_value_frames(commercial_electricity_cons,
                                           household_electricity_cons,
                                           school_electricity_cons),
                 on='datetime'). \
            rename({'value': get_elec_cons_key(agent['Name'])}). \
            join(add_datetime_value_frames(commercial_space_heating_cons,
                                           residential_space_heating_cons,
                                           school_space_heating_cons),
                 on='datetime'). \
            rename({'value': get_space_heat_cons_key(agent['Name'])}). \
            join(add_datetime_value_frames(commercial_hot_tap_water_cons,
                                           residential_hot_tap_water_cons,
                                           school_hot_tap_water_cons),
                 on='datetime'). \
            rename({'value': get_hot_tap_water_cons_key(agent['Name'])})

    end = time.time()
    time_elapsed = end - start
    logger.debug('Finished work on \'{}\', took {:.2f} seconds'.format(agent['Name'], time_elapsed))
    return output_per_actor, time_elapsed


def find_agent_in_other_data_sets(agent_dict: Dict[str, Any], mock_data_constants: Dict[str, Any],
                                  all_data_sets: Dict[MockDataKey, pl.DataFrame]) -> pl.DataFrame:
    """Introduced in RES-216 - looking through other data sets, if this agent was present there, we can re-use that,
    instead of running the generation step again. This saves time. If no usable data is found, the returned DataFrame
    will be empty."""
    data_to_reuse = pl.DataFrame()
    found_cons_data = False
    for mock_data_key, mock_data in all_data_sets.items():
        set_of_building_agents = mock_data_key.building_agents_frozen_set
        other_mock_data_constants = dict(mock_data_key.mock_data_constants)
        for other_agent in set_of_building_agents:
            other_agent_dict = dict(other_agent)

            if (not found_cons_data) and \
                    all_parameters_match(agent_dict, other_agent_dict, mock_data_constants, other_mock_data_constants):
                # All parameters relating to generating energy usage data are the same
                logger.debug('For agent \'{}\' found energy consumption data to re-use'.format(agent_dict['Name']))
                found_cons_data = True
                cons_data = mock_data.select([pl.col(get_elec_cons_key(other_agent_dict['Name'])),
                                              pl.col(get_space_heat_cons_key(other_agent_dict['Name'])),
                                              pl.col(get_hot_tap_water_cons_key(other_agent_dict['Name']))])
                # Make sure that the datetime column is present
                if 'datetime' not in data_to_reuse.columns:
                    data_to_reuse = data_to_reuse.with_column(mock_data['datetime'])
                data_to_reuse = pl.concat((data_to_reuse, cons_data), how='horizontal')
    return data_to_reuse


def all_parameters_match(agent_dict: Dict[str, Any], other_agent_dict: Dict[str, Any],
                         mock_data_constants: Dict[str, Any], other_mock_data_constants: Dict[str, Any]) -> bool:
    """
    Check if all parameters used for generating mock data for a given pair of agents are the same.
    Looks at fields in the agent dictionaries themselves, but also the relevant mock data constants. If an agent has
    no commercial areas, for example, then it doesn't matter that mock data constants relating to commercial areas are
    different.
    """
    if agent_parameters_match(agent_dict, other_agent_dict):
        relevant_mock_data_generation_constants_match: bool = True
        if get_if_exists_else(agent_dict, 'FractionCommercial', 0) > 0 and \
                not all_fields_match(mock_data_constants, other_mock_data_constants,
                                     ['CommercialElecKwhPerYearM2',
                                      'CommercialElecRelativeErrorStdDev',
                                      'CommercialSpaceHeatKwhPerYearM2',
                                      'CommercialHotTapWaterKwhPerYearM2',
                                      'CommercialHotTapWaterRelativeErrorStdDev']):
            relevant_mock_data_generation_constants_match = False

        if get_if_exists_else(agent_dict, 'FractionSchool', 0) > 0 and \
                not all_fields_match(mock_data_constants, other_mock_data_constants,
                                     ['SchoolElecKwhPerYearM2',
                                      'SchoolElecRelativeErrorStdDev',
                                      'SchoolSpaceHeatKwhPerYearM2',
                                      'SchoolHotTapWaterKwhPerYearM2',
                                      'SchoolHotTapWaterRelativeErrorStdDev']):
            relevant_mock_data_generation_constants_match = False

        fraction_residential = 1 - get_if_exists_else(agent_dict, 'FractionCommercial', 0) - \
            get_if_exists_else(agent_dict, 'FractionSchool', 0)
        if fraction_residential > 0 and not all_fields_match(mock_data_constants, other_mock_data_constants,
                                                             ['ResidentialElecKwhPerYearM2Atemp',
                                                              'ResidentialSpaceHeatKwhPerYearM2',
                                                              'ResidentialHotTapWaterKwhPerYearM2',
                                                              'ResidentialHeatingRelativeErrorStdDev']):
            relevant_mock_data_generation_constants_match = False

        return relevant_mock_data_generation_constants_match
    return False


def agent_parameters_match(agent_dict: Dict[str, Any], other_agent_dict: Dict[str, Any]) -> bool:
    fields_to_check = ['Name', 'GrossFloorArea', 'FractionCommercial', 'FractionSchool']
    return all_fields_match(agent_dict, other_agent_dict, fields_to_check)


def all_fields_match(dict_1: dict, dict_2: dict, keys_list: Iterable) -> bool:
    for key in keys_list:
        if get_if_exists_else(dict_1, key, 0) != get_if_exists_else(dict_2, key, 0):
            return False
    return True


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
    config_from_file = read_config()

    run(config_from_file)
