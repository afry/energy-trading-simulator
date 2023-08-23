import functools
import logging
import pickle
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import polars as pl

logger = logging.getLogger(__name__)

"""Here goes functions that are used both for generating mock data, and for loading that data when starting simulations.
"""


@dataclass(frozen=True)
class MockDataKey:
    building_agents_frozen_set: frozenset
    mock_data_constants: frozenset


def load_existing_data_sets(file_path: str) -> Dict[MockDataKey, pl.DataFrame]:
    try:
        all_data_sets = pickle.load(open(file_path, 'rb'))
    except FileNotFoundError:
        logger.info('Did not find existing mock data file, assuming it is empty')
        all_data_sets = {}
    return all_data_sets


def get_all_building_agents(all_agents: List[Dict]) -> Tuple[Set, float]:
    """
    Gets all building agents from all_agents, and also returns the total gross floor area, summed over all building
    agents.
    @param all_agents: A list of dictionaries, each dict representing an agent
    @return: building_agents: Set of frozen sets, total_gross_floor_area: a float
    """
    total_gross_floor_area = 0
    building_agents = set()
    for agent in all_agents:
        agent_type = agent["Type"]
        if agent_type == "BuildingAgent":
            key = frozenset(agent.items())
            building_agents.add(key)
            total_gross_floor_area = total_gross_floor_area + agent['GrossFloorArea']
    return building_agents, total_gross_floor_area


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
