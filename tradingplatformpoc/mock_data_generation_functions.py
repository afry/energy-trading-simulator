import datetime
import logging
import pickle
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import polars as pl

logger = logging.getLogger(__name__)

"""Here goes functions that are used both for generating mock data, and for loading that data when starting simulations.
"""

# Constants used in the 'is_break' method. Better to instantiate these here, since is_break is called many times, and
# instantiating these over and over again is really unnecessary.
# Year doesn't really matter, we'll only use the day-of-year
JUST_SOME_NONE_LEAP_YEAR = 2019
# Summer break 15/6 - 15/8
SUMMER_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 6, 15).timetuple().tm_yday
SUMMER_END = SUMMER_START + 60
# Fall break 1/11 - 7/11
FALL_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 11, 1).timetuple().tm_yday
FALL_END = FALL_START + 7
# Christmas break 22/12 - 2/1
CHRISTMAS_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 12, 22).timetuple().tm_yday
CHRISTMAS_END = CHRISTMAS_START + 14
# Sportlov 15/2 - 21/2
SPRING_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 2, 1).timetuple().tm_yday
SPRING_END = SPRING_START + 7
# Easter 07/04 - 14/04
# Easter moves yearly, but the since we are only interested in capturing the feature
# of a week off school sometime in mid-spring, we simply chose an average date (April 7th)
EASTER_START = datetime.datetime(JUST_SOME_NONE_LEAP_YEAR, 4, 7).timetuple().tm_yday
EASTER_END = EASTER_START + 7

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
    default_pv_efficiency: float


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
    if not (8 <= timestamp.hour < 17):
        return 0.5
    return 1


def is_break(timestamp: datetime.datetime):
    # We compare the day-of-year to some pre-defined starts and ends of break periods
    day_of_year = timestamp.timetuple().tm_yday

    # Return true if timestamp falls on break, false if not
    if SUMMER_START <= day_of_year <= SUMMER_END:
        return True

    if FALL_START <= day_of_year <= FALL_END:
        return True

    if CHRISTMAS_START <= day_of_year <= CHRISTMAS_END:
        return True

    if SPRING_START <= day_of_year <= SPRING_END:
        return True

    if EASTER_START <= day_of_year <= EASTER_END:
        return True
