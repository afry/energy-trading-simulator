import functools
import hashlib
import logging
from typing import Any, Dict, List

import polars as pl

from tradingplatformpoc.sql.mock_data.crud import check_if_agent_equivalent_in_db, db_to_mock_data_df

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
        logger.info('No DataFrames to join!')
        return pl.DataFrame()


def get_equivalent_mock_data(mock_data_id: str, old_agent_id: str, new_agent_id: str) -> pl.DataFrame:
    """
    Gets the specified mock data pl.DataFrame by mock_data_id. The column names will include old_agent_id, which will
    be replaced by new_agent_id.
    """
    existing_df = db_to_mock_data_df(mock_data_id)
    # Rename columns
    if len([col for col in existing_df.columns if old_agent_id in col]) == 0:
        logger.warning('Old agent ID {} not found in mock DataFrame! Column names were {}'.
                       format(old_agent_id, existing_df.columns))
    return existing_df.select(
        pl.all().map_alias(lambda col_name: col_name.replace(old_agent_id, new_agent_id))
    )


def get_mock_ids_to_reuse(block_agents_not_pre_existing: List[Dict[str, Any]], mock_data_constants: Dict[str, Any],
                          reuse: bool) -> Dict[str, Dict[str, str]]:
    """
    Goes through the agents in 'block_agents_not_pre_existing', and looks for agents in the database for which we
    already have mock data, and are identical from a mock data perspective (identical building size and constitution,
    but things like heat pumps can be different).
    Returns a dict with:
    Keys - agent ID (agents in the config we're going to create/fetch mock data for)
    Values - 'mock_data_id' and 'agent_id' of agents that are equivalent, from a mock data perspective, to the key
        agent, so the key agent can use the mock data with ID mock_data_id
    """
    mock_id_to_reuse_for_agent_id: Dict[str, Dict[str, str]] = {}
    if reuse:
        for block_agent in block_agents_not_pre_existing:
            equivalents = check_if_agent_equivalent_in_db(block_agent, mock_data_constants)
            if equivalents is not None:
                mock_id_to_reuse_for_agent_id[block_agent['db_id']] = equivalents
    return mock_id_to_reuse_for_agent_id


def calculate_seed_from_string(some_string: str) -> int:
    """
    Hashes the string, and truncates the value to a 32-bit integer, since that is what seeds are allowed to be.
    __hash__() is non-deterministic, so we use hashlib.
    """
    bytes_to_hash = some_string.encode('utf-8')
    hashed_hexadecimal = hashlib.sha256(bytes_to_hash).hexdigest()
    very_big_int = int(hashed_hexadecimal, 16)
    return very_big_int & 0xFFFFFFFF
