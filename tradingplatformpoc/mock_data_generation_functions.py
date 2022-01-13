import logging
import pickle

logger = logging.getLogger(__name__)

"""Here goes functions that are used both for generating mock data, and for loading that data when starting simulations.
"""


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


def get_pv_prod_key(agent_name: str):
    return agent_name + '_pv_prod'
