import logging
import pickle

logger = logging.getLogger(__name__)

"""Here goes functions that are used both for generating mock data, and for loading that data when starting simulations.
"""


def load_existing_data_sets(file_path):
    try:
        all_data_sets = pickle.load(open(file_path, 'rb'))
    except FileNotFoundError:
        logger.info('Did not find existing mock data file, assuming it is empty')
        all_data_sets = {}
    return all_data_sets


def get_all_building_agents(config_data):
    total_gross_floor_area = 0
    building_agents = set()
    for agent in config_data["Agents"]:
        agent_type = agent["Type"]
        if agent_type == "BuildingAgent":
            key = frozenset(agent.items())
            building_agents.add(key)
            total_gross_floor_area = total_gross_floor_area + agent['GrossFloorArea']
    return building_agents, total_gross_floor_area


def get_elec_cons_key(agent_name):
    return agent_name + '_elec_cons'


def get_pv_prod_key(agent_name):
    return agent_name + '_pv_prod'
