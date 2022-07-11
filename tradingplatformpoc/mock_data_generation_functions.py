import datetime
import logging
import pickle
from dataclasses import dataclass
from typing import Any, Dict, Set, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

"""Here goes functions that are used both for generating mock data, and for loading that data when starting simulations.
"""

COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR = {
    0: 0.2,
    1: 0.2,
    2: 0.2,
    3: 0.2,
    4: 0.2,
    5: 0.2,
    6: 0.3,
    7: 0.5,
    8: 0.7,
    9: 0.91,
    10: 0.92,
    11: 0.93,
    12: 0.94,
    13: 0.95,
    14: 0.96,
    15: 0.97,
    16: 0.98,
    17: 0.99,
    18: 1.0,
    19: 0.6,
    20: 0.2,
    21: 0.2,
    22: 0.2,
    23: 0.2
}


@dataclass(frozen=True)
class MockDataKey:
    building_agents_frozen_set: frozenset
    area_info_frozen_set: frozenset


def load_existing_data_sets(file_path: str) -> Dict[MockDataKey, pd.DataFrame]:
    try:
        all_data_sets = pickle.load(open(file_path, 'rb'))
    except FileNotFoundError:
        logger.info('Did not find existing mock data file, assuming it is empty')
        all_data_sets = {}
    return all_data_sets


def get_all_building_agents(config_data: Dict[str, Any]) -> Tuple[Set, float]:
    """
    Gets all building agents specified in config_data, and also returns the total gross floor area, summed
    over all building agents.
    @param config_data: A dictionary
    @return: building_agents: Set of frozen sets, total_gross_floor_area: a float
    """
    total_gross_floor_area = 0
    building_agents = set()
    for agent in config_data["Agents"]:
        agent_type = agent["Type"]
        if agent_type == "BuildingAgent":
            key = frozenset(agent.items())
            building_agents.add(key)
            total_gross_floor_area = total_gross_floor_area + agent['GrossFloorArea']
    return building_agents, total_gross_floor_area


def get_elec_cons_key(agent_name: str):
    return agent_name + '_elec_cons'


def get_space_heat_cons_key(agent_name: str):
    return agent_name + '_space_heat_cons'


def get_hot_tap_water_cons_key(agent_name: str):
    return agent_name + '_hot_tap_water_cons'


def get_pv_prod_key(agent_name: str):
    return agent_name + '_pv_prod'


def get_commercial_electricity_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    return COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR[timestamp.hour]


def get_commercial_heating_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    """Assuming opening hours 9-20, roughly similar to COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR"""
    if 9 <= timestamp.hour < 20:
        return 1.0
    else:
        return 0.5


def get_school_heating_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    """Assuming opening hours 8-17:00 except for weekends and breaks"""
    if timestamp.weekday() == 5 or timestamp.weekday() == 6:  # Saturday or sunday
        return 0.5
    if is_break(timestamp):
        return 0.5
    if not(8 <= timestamp.hour < 17):
        return 0.5
    return 1


def is_break(timestamp: datetime.datetime):
    current_year = timestamp.year
    # Removing timezone so we can compare to timezone-naive datetimes. This method is just approximating break times
    # anyway, so an hour back or forth doesn't matter too much
    timestamp = timestamp.replace(tzinfo=None)

    # Define breaks, return true if timestamp falls on break, false if not
    # Summer break 15/6 - 15/8
    summer_start = datetime.datetime(current_year, 6, 1)
    summer_length = datetime.timedelta(days=60)

    if summer_start <= timestamp <= summer_start + summer_length:
        return True

    # Fall break 1/11 - 7/11
    fall_start = datetime.datetime(current_year, 11, 1)
    fall_length = datetime.timedelta(days=7)
    if fall_start <= timestamp <= fall_start + fall_length:
        return True

    # Christmas break 22/12 - 2/1
    christmas_start = datetime.datetime(current_year, 12, 22)
    christmas_length = datetime.timedelta(days=14)
    if christmas_start <= timestamp <= christmas_start + christmas_length:
        return True

    # Sportlov 15/2 - 21/2
    spring_start = datetime.datetime(current_year, 2, 1)
    spring_length = datetime.timedelta(days=7)
    if spring_start <= timestamp <= spring_start + spring_length:
        return True

    # Easter 07/04 - 14/04
    # Easter moves yearly, but the since we are only interested in capturing the feature
    # of a week off school sometime in mid-spring, we simply chose an average date.
    easter_start = datetime.datetime(current_year, 4, 7)
    easter_length = datetime.timedelta(days=7)
    if easter_start <= timestamp <= easter_start + easter_length:
        return True

    return False
