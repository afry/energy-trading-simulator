import logging
import pickle

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


def load_existing_data_sets(file_path: str):
    try:
        all_data_sets = pickle.load(open(file_path, 'rb'))
    except FileNotFoundError:
        logger.info('Did not find existing mock data file, assuming it is empty')
        all_data_sets = {}
    return all_data_sets


def get_all_residential_building_agents(config_data: dict):
    """
    Gets all residential building agents specified in config_data, and also returns the total gross floor area, summed
    over all residential building agents.
    @param config_data: A dictionary
    @return: residential_building_agents: Set of dictionaries, total_gross_floor_area: a float
    """
    total_gross_floor_area = 0
    residential_building_agents = set()
    for agent in config_data["Agents"]:
        agent_type = agent["Type"]
        if agent_type == "ResidentialBuildingAgent":
            key = frozenset(agent.items())
            residential_building_agents.add(key)
            total_gross_floor_area = total_gross_floor_area + agent['GrossFloorArea']
    return residential_building_agents, total_gross_floor_area


def get_elec_cons_key(agent_name: str):
    return agent_name + '_elec_cons'


def get_heat_cons_key(agent_name: str):
    return agent_name + '_heat_cons'


def get_pv_prod_key(agent_name: str):
    return agent_name + '_pv_prod'


def get_commercial_electricity_consumption_hourly_factor(hour: int) -> float:
    return COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR[hour]
