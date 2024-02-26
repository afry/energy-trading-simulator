import functools
import hashlib
import logging
from typing import List

import polars as pl

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


def calculate_seed_from_string(some_string: str) -> int:
    """
    Hashes the string, and truncates the value to a 32-bit integer, since that is what seeds are allowed to be.
    __hash__() is non-deterministic, so we use hashlib.
    """
    bytes_to_hash = some_string.encode('utf-8')
    hashed_hexadecimal = hashlib.sha256(bytes_to_hash).hexdigest()
    very_big_int = int(hashed_hexadecimal, 16)
    return very_big_int & 0xFFFFFFFF
