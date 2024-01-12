import functools
import hashlib
import logging
from typing import Any, Dict, Iterable, List

import polars as pl

from tradingplatformpoc.trading_platform_utils import get_if_exists_else

logger = logging.getLogger(__name__)

"""
Here goes mock data generation util functions.
"""


def get_elec_cons_key(agent_id: str):
    return agent_id + '_elec_cons'


def get_space_heat_cons_key(agent_id: str):
    return agent_id + '_space_heat_cons'


def get_hot_tap_water_cons_key(agent_id: str):
    return agent_id + '_hot_tap_water_cons'


def get_pv_prod_key(agent_id: str):
    return agent_id + '_pv_prod'


def get_cooling_cons_key(agent_id: str):
    return agent_id + '_cooling_cons'


def join_list_of_polar_dfs(dfs: List[pl.DataFrame]) -> pl.DataFrame:
    if len(dfs) > 1:
        return functools.reduce(lambda left, right: left.join(right, on='datetime'), dfs)
    elif len(dfs) == 1:
        return dfs[0]
    else:
        logger.warning('No DataFrames to join!')
        return pl.DataFrame()


# TODO: Question: Cann we still use this function somehow?
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
                                                             ['HouseholdElecKwhPerYearM2Atemp',
                                                              'ResidentialPropertyElecKwhPerYearM2Atemp',
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
