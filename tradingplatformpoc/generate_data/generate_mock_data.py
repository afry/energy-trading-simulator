import logging
import os
from typing import Any, Dict, List, Tuple, Union

import pandas as pd

from pkg_resources import resource_filename

import polars as pl

from statsmodels.regression.linear_model import RegressionResultsWrapper

from tradingplatformpoc.compress import bz2_decompress_pickle
from tradingplatformpoc.database import bulk_insert
from tradingplatformpoc.generate_data.generation_functions.common import add_datetime_value_frames, constants, \
    extract_datetime_features_from_inputs_df
from tradingplatformpoc.generate_data.generation_functions.non_residential.commercial import \
    get_commercial_cooling_consumption_factor, get_commercial_electricity_consumption_hourly_factor, \
    get_commercial_heating_consumption_hourly_factor
from tradingplatformpoc.generate_data.generation_functions.non_residential.common import simulate_area_electricity, \
    simulate_cooling, simulate_heating
from tradingplatformpoc.generate_data.generation_functions.non_residential.office import read_office_dicts, \
    simulate_office_based_on_daily, simulate_office_based_on_hourly
from tradingplatformpoc.generate_data.generation_functions.non_residential.school import \
    get_school_heating_consumption_hourly_factor
from tradingplatformpoc.generate_data.generation_functions.residential.electricity import \
    property_electricity, simulate_household_electricity_aggregated
from tradingplatformpoc.generate_data.generation_functions.residential.heating import simulate_residential_total_heating
from tradingplatformpoc.generate_data.mock_data_utils import \
    calculate_seed_from_string, get_cooling_cons_key, get_elec_cons_key, get_equivalent_mock_data, \
    get_hot_tap_water_cons_key, get_mock_ids_to_reuse, get_space_heat_cons_key, join_list_of_polar_dfs
from tradingplatformpoc.sql.agent.crud import get_block_agent_dicts_from_id_list
from tradingplatformpoc.sql.config.crud import get_all_agent_name_id_pairs_in_config, get_mock_data_constants
from tradingplatformpoc.sql.input_data.crud import read_inputs_df_for_mock_data_generation
from tradingplatformpoc.sql.mock_data.crud import db_to_mock_data_df, get_mock_data_agent_pairs_in_db, \
    mock_data_df_to_db_dict
from tradingplatformpoc.sql.mock_data.models import MockData as TableMockData
from tradingplatformpoc.trading_platform_utils import get_if_exists_else

DATA_PATH = 'tradingplatformpoc.data'

# Will use these to set random seed.
RESIDENTIAL_HEATING_SEED_SUFFIX = "RH"
COMMERCIAL_ELECTRICITY_SEED_SUFFIX = "CE"
COMMERCIAL_HEATING_SEED_SUFFIX = "CH"
SCHOOL_HEATING_SEED_SUFFIX = "SH"
SCHOOL_ELECTRICITY_SEED_SUFFIX = "SE"
OFFICE_HEATING_SEED_SUFFIX = "OH"
OFFICE_ELECTRICITY_SEED_SUFFIX = "OE"

"""
This script generates the following, for BlockAgents:
*Household electricity consumption data
*Commercial electricity consumption data
*School electricity consumption data
*Office electricity consumption data
*Residential hot water consumption data
*Commercial hot water consumption data
*School hot water consumption data
*Office hot water consumption data
*Residential space heating consumption data
*Commercial space heating consumption data
*School space heating consumption data
*Office space heating consumption data
*Commercial cooling consumption data
*Office cooling consumption data
It stores such data in the mock_data table in the database.
For some more information, see the "docs" folder.
"""

logger = logging.getLogger(__name__)


def get_generated_mock_data(config_id: str) -> pd.DataFrame:
    """
    Fetch mock data if it exists, else generate it.
    @param config_id: Config id in db
    @return: A pd.DataFrame containing mock data for block agents
    """
    logger.info("Running mock data generation.")
    data_set = run(config_id)
    logger.info("Finished getting mock data.")
    return data_set.to_pandas().set_index('datetime')


def run(config_id: str, reuse: bool = True) -> Union[pl.DataFrame, pl.LazyFrame]:
    """
    Fetch mock data if it exists, else generate it.
    @param config_id: Config id in db
    @param reuse: If true, will re-use existing mock data found in database, where appropriate
    @return: A pl.DataFrame or pl.LazyFrame containing mock data for block agents
    """
    agent_name_id_pairs = get_all_agent_name_id_pairs_in_config(config_id)
    mock_data_constants = get_mock_data_constants(config_id)
    if mock_data_constants is None:
        raise RuntimeError('No mock data constants found for config ID {}'.format(config_id))
    agent_ids_in_config = list(agent_name_id_pairs.values())
    mock_data_agent_ids_dict = get_mock_data_agent_pairs_in_db(agent_ids_in_config, mock_data_constants)
    if reuse:
        agent_ids_without_mock_data = [agent_id for agent_id in agent_ids_in_config
                                       if agent_id not in mock_data_agent_ids_dict.values()]
    else:
        agent_ids_without_mock_data = agent_ids_in_config
    block_agents_not_pre_existing = get_block_agent_dicts_from_id_list(agent_ids_without_mock_data)
    mock_id_to_reuse_for_agent_id = get_mock_ids_to_reuse(block_agents_not_pre_existing, mock_data_constants, reuse)
    block_agents_to_simulate_for = [ba for ba in block_agents_not_pre_existing
                                    if ba['db_id'] not in mock_id_to_reuse_for_agent_id.keys()]

    existing_mock_data_ids = mock_data_agent_ids_dict.keys()
    
    if ((len(existing_mock_data_ids) == 0)
            and (len(block_agents_to_simulate_for) == 0)
            and (len(mock_id_to_reuse_for_agent_id) == 0)):
        logger.info('No mock data needed.')
        return pl.DataFrame(columns=['datetime'])

    if len(block_agents_to_simulate_for) > 0:
        # Simulate mock data for block agents
        dfs_new = simulate_for_agents(block_agents_to_simulate_for, mock_data_constants)

        # Insert simulated mock data into database
        mock_data_dicts = [mock_data_df_to_db_dict(key, mock_data_constants, value) for key, value in dfs_new.items()]
        bulk_insert(TableMockData, mock_data_dicts)
        logger.info('Mock data inserted into database.')
        
        # Join dataframes
        logger.info('Joining simulated dataframes.')
        joined_dfs_new = join_list_of_polar_dfs(list(dfs_new.values()))

    else:
        logger.info('Found no new agents to simulate data for')
        joined_dfs_new = pl.DataFrame()
        
    # Fetch rest of data from database
    dfs_from_db: List[pl.DataFrame] = []
    for mock_data_id in existing_mock_data_ids:
        dfs_from_db.append(db_to_mock_data_df(mock_data_id))
    mock_data_to_insert: List[dict] = []
    for agent_id, equivalents in mock_id_to_reuse_for_agent_id.items():
        renamed_df = get_equivalent_mock_data(equivalents['mock_data_id'], equivalents['agent_id'], agent_id)
        # This mock data already exists in the DB, but with a different agent_id. Save it as a new row with this agent
        # ID, so that it can be used in the UI
        db_dict = mock_data_df_to_db_dict(agent_id, mock_data_constants, renamed_df)
        mock_data_to_insert.append(db_dict)
        # Finally add the dataframe to the list
        dfs_from_db.append(renamed_df)
    bulk_insert(TableMockData, mock_data_to_insert)

    logger.info('Joining dataframes from database.')
    joined_dfs_from_db = join_list_of_polar_dfs(dfs_from_db)

    # Combine newly simulated data with data from database
    if (not joined_dfs_new.is_empty()) & (not joined_dfs_from_db.is_empty()):
        return joined_dfs_new.join(joined_dfs_from_db, on='datetime')
    elif (joined_dfs_new.is_empty()) & (not joined_dfs_from_db.is_empty()):
        return joined_dfs_from_db
    elif (not joined_dfs_new.is_empty()) & (joined_dfs_from_db.is_empty()):
        return joined_dfs_new
    else:
        logger.error('No mock data to return!')
        raise Exception('Mock data neither generated nor found!')


def simulate_for_agents(agent_dicts: List[Dict[str, Any]], mock_data_constants: Dict[str, Any], key='db_id'
                        ) -> Dict[str, pl.DataFrame]:
    # So we have established that we need to generate new mock data.
    logger.info('Beginning mock data generation for {} agents'.format(len(agent_dicts)))

    # Load model
    model = bz2_decompress_pickle(resource_filename(DATA_PATH, 'models/household_electricity_model.pbz2'))
    logger.debug('Model loaded')

    # Load dicts for office data
    office_elec_dict, office_hot_water_dict = read_office_dicts()

    # Read input data: Temperature, irradiation and heat consumption
    df_inputs_pandas = read_inputs_df_for_mock_data_generation()
    df_inputs = extract_datetime_features_from_inputs_df(df_inputs_pandas)
    logger.debug('Input data loaded')

    # Extract indices
    output_per_actor = pl.DataFrame({'datetime': df_inputs['datetime']})
    n_rows = df_inputs.height
    lazy_inputs = df_inputs.lazy()

    # Dictionary to fill with dataframes, starting with empty to simplify join
    dfs_new: Dict[str, pl.DataFrame] = {}
    # Generation loop
    for agent_dict in agent_dicts:

        logger.info('Generating new data for ' + agent_dict[key])
        output_per_block = simulate(mock_data_constants, agent_dict, lazy_inputs,
                                    n_rows, model, output_per_actor.clone(), key,
                                    office_elec_dict, office_hot_water_dict)
        dfs_new[agent_dict[key]] = output_per_block
    
    return dfs_new


def simulate(mock_data_constants: Dict[str, Any], agent: dict, df_inputs: pl.LazyFrame, n_rows: int,
             model: RegressionResultsWrapper, output_per_actor: pl.DataFrame, key: str,
             office_elec_dict: Dict[Tuple[int, int], float], office_hot_water_dict: Dict[Tuple[int, int], float]) \
        -> pl.DataFrame:
    """
    Simulate mock data for agent and mock data constants.
    """
    logger.debug('Starting work on \'{}\''.format(agent[key]))
        
    # Seeds
    agent_as_str = str(sorted({k: v for k, v in agent.items() if k != key}.items()))
    seed_residential_electricity = calculate_seed_from_string(agent_as_str)
    seed_residential_heating = calculate_seed_from_string(agent_as_str + RESIDENTIAL_HEATING_SEED_SUFFIX)
    seed_commercial_electricity = calculate_seed_from_string(agent_as_str + COMMERCIAL_ELECTRICITY_SEED_SUFFIX)
    seed_commercial_heating = calculate_seed_from_string(agent_as_str + COMMERCIAL_HEATING_SEED_SUFFIX)
    seed_school_electricity = calculate_seed_from_string(agent_as_str + SCHOOL_ELECTRICITY_SEED_SUFFIX)
    seed_school_heating = calculate_seed_from_string(agent_as_str + SCHOOL_HEATING_SEED_SUFFIX)
    seed_office_electricity = calculate_seed_from_string(agent_as_str + OFFICE_ELECTRICITY_SEED_SUFFIX)
    seed_office_heating = calculate_seed_from_string(agent_as_str + OFFICE_HEATING_SEED_SUFFIX)

    # Fraction of area in commercial, school and residential
    fraction_commercial = get_if_exists_else(agent, 'FractionCommercial', 0)
    fraction_school = get_if_exists_else(agent, 'FractionSchool', 0)
    fraction_office = get_if_exists_else(agent, 'FractionOffice', 0)
    non_residential = fraction_commercial + fraction_school + fraction_office
    logger.debug("Total non-residential fraction {}".format(non_residential))
    if non_residential > 1:
        logger.error("Total non-residential fractions for agent {} larger than 100%".format(agent[key]))
        exit(1)
    fraction_residential = 1.0 - non_residential

    electricity_consumption: List[Union[pl.DataFrame, pl.LazyFrame]] = []
    space_heating_consumption: List[Union[pl.DataFrame, pl.LazyFrame]] = []
    hot_tap_water_consumption: List[Union[pl.DataFrame, pl.LazyFrame]] = []
    cooling_consumption: List[Union[pl.DataFrame, pl.LazyFrame]] = []

    # COMMERCIAL
    if fraction_commercial > 0:
        commercial_atemp = agent['Atemp'] * fraction_commercial

        electricity_consumption.append(simulate_area_electricity(
            commercial_atemp, seed_commercial_electricity, df_inputs,
            mock_data_constants['CommercialElecKwhPerYearM2'], mock_data_constants['RelativeErrorStdDev'],
            get_commercial_electricity_consumption_hourly_factor, n_rows))

        commercial_space_heating_cons, commercial_hot_tap_water_cons = simulate_heating(
            mock_data_constants, commercial_atemp, 'CommercialSpaceHeatKwhPerYearM2',
            'CommercialHotTapWaterKwhPerYearM2', get_commercial_heating_consumption_hourly_factor,
            seed_commercial_heating, df_inputs, n_rows)
        space_heating_consumption.append(commercial_space_heating_cons)
        hot_tap_water_consumption.append(commercial_hot_tap_water_cons)

        commercial_cooling = simulate_cooling(commercial_atemp,
                                              mock_data_constants['CommercialCoolKwhPerYearM2'],
                                              mock_data_constants['RelativeErrorStdDev'],
                                              get_commercial_cooling_consumption_factor,
                                              seed_commercial_electricity, df_inputs, n_rows)
        cooling_consumption.append(commercial_cooling)

    # SCHOOL
    if fraction_school > 0:
        school_atemp_m2 = agent['Atemp'] * fraction_school

        electricity_consumption.append(
            simulate_area_electricity(
                school_atemp_m2, seed_school_electricity, df_inputs,
                mock_data_constants['SchoolElecKwhPerYearM2'], mock_data_constants['RelativeErrorStdDev'],
                get_school_heating_consumption_hourly_factor, n_rows))

        school_space_heating_cons, school_hot_tap_water_cons = simulate_heating(
            mock_data_constants, school_atemp_m2, 'SchoolSpaceHeatKwhPerYearM2',
            'SchoolHotTapWaterKwhPerYearM2', get_school_heating_consumption_hourly_factor,
            seed_school_heating, df_inputs, n_rows)
        space_heating_consumption.append(school_space_heating_cons)
        hot_tap_water_consumption.append(school_hot_tap_water_cons)

        school_cooling = constants(df_inputs, 0)
        cooling_consumption.append(school_cooling)

    # OFFICE
    if fraction_office > 0:
        office_atemp_m2 = agent['Atemp'] * fraction_office

        electricity_consumption.append(
            simulate_office_based_on_daily(
                office_atemp_m2, mock_data_constants['RelativeErrorStdDev'],
                mock_data_constants['OfficeElecKwhPerYearM2'], seed_office_heating,
                df_inputs, n_rows, office_elec_dict))

        office_hot_tap_water_cons = simulate_office_based_on_daily(
            office_atemp_m2, mock_data_constants['RelativeErrorStdDev'],
            mock_data_constants['OfficeHotTapWaterKwhPerYearM2'], seed_office_heating,
            df_inputs, n_rows, office_hot_water_dict)
        office_space_heating_cons = simulate_office_based_on_hourly(office_atemp_m2,
                                                                    mock_data_constants['RelativeErrorStdDev'],
                                                                    mock_data_constants['OfficeSpaceHeatKwhPerYearM2'],
                                                                    'office_space_heating',
                                                                    seed_office_heating, df_inputs, n_rows)
        space_heating_consumption.append(office_space_heating_cons)
        hot_tap_water_consumption.append(office_hot_tap_water_cons)

        office_cooling = simulate_office_based_on_hourly(office_atemp_m2,
                                                         mock_data_constants['RelativeErrorStdDev'],
                                                         mock_data_constants['OfficeCoolKwhPerYearM2'],
                                                         'office_cooling',
                                                         seed_office_electricity, df_inputs, n_rows)
        cooling_consumption.append(office_cooling)

    # RESIDENTIAL
    if fraction_residential > 0:
        residential_atemp = agent['Atemp'] * fraction_residential

        household_el = simulate_household_electricity_aggregated(df_inputs, model, residential_atemp,
                                                                 seed_residential_electricity, n_rows,
                                                                 mock_data_constants['HouseholdElecKwhPerYearM2Atemp'])
        property_el = property_electricity(df_inputs, residential_atemp, n_rows,
                                           mock_data_constants['ResidentialPropertyElecKwhPerYearM2Atemp'])
        electricity_consumption.append(add_datetime_value_frames([household_el, property_el]))

        residential_space_heating_cons, residential_hot_tap_water_cons = simulate_residential_total_heating(
            mock_data_constants, df_inputs, n_rows, residential_atemp, seed_residential_heating)
        space_heating_consumption.append(residential_space_heating_cons)
        hot_tap_water_consumption.append(residential_hot_tap_water_cons)

        residential_cooling = constants(df_inputs, 0)
        cooling_consumption.append(residential_cooling)

    logger.debug("Adding output for agent {}".format(agent[key]))
    # Note: Here we join a normal DataFrame (output_per_actor) with LazyFrames
    output_per_actor = output_per_actor. \
        join(add_datetime_value_frames(electricity_consumption), on='datetime'). \
        rename({'value': get_elec_cons_key(agent[key])}). \
        join(add_datetime_value_frames(space_heating_consumption), on='datetime'). \
        rename({'value': get_space_heat_cons_key(agent[key])}). \
        join(add_datetime_value_frames(hot_tap_water_consumption), on='datetime'). \
        rename({'value': get_hot_tap_water_cons_key(agent[key])}). \
        join(add_datetime_value_frames(cooling_consumption), on='datetime'). \
        rename({'value': get_cooling_cons_key(agent[key])})

    return output_per_actor


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

    run('default', reuse=False)
