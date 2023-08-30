import functools
import logging
from typing import List

import polars as pl

logger = logging.getLogger(__name__)

"""Here goes functions that are used both for generating mock data, and for loading that data when starting simulations.
"""


def get_elec_cons_key(agent_id: str):
    return agent_id + '_elec_cons'


def get_space_heat_cons_key(agent_id: str):
    return agent_id + '_space_heat_cons'


def get_hot_tap_water_cons_key(agent_id: str):
    return agent_id + '_hot_tap_water_cons'


def get_pv_prod_key(agent_id: str):
    return agent_id + '_pv_prod'


def join_list_of_polar_dfs(dfs: List[pl.DataFrame]) -> pl.DataFrame:
    if len(dfs) > 1:
        return functools.reduce(lambda left, right: left.join(right, on='datetime'), dfs)
    elif len(dfs) == 1:
        return dfs[0]
    else:
        logger.warning('No DataFrames to join!')
        return pl.DataFrame()
