import json
import pickle

import pandas as pd

from pkg_resources import resource_filename

from tradingplatformpoc.mock_data_generation_functions import get_all_residential_building_agents, get_elec_cons_key, \
    get_heat_cons_key

DATA_PATH = 'tradingplatformpoc.data'
CONFIG_FILE = 'jonstaka.json'
IN_PICKLE = resource_filename(DATA_PATH, 'mock_datas.pickle')
AGENT_TO_LOOK_AT = 'ResidentialBuildingAgentBC1'

"""
A utility script, to examine the generated mock data.
Goes through the datasets in the IN_PICKLE file defined above, takes out the electricity consumption for a given
agent, and saves to a data frame, so that one can easily compare the electricity consumption for an agent using
different configurations.
"""

# Open config file
with open(resource_filename(DATA_PATH, CONFIG_FILE), "r") as json_file:
    config_data = json.load(json_file)
residential_building_agents, total_gross_floor_area = get_all_residential_building_agents(config_data)
# The residential building agents in the current config:
current_config_rbas = frozenset(residential_building_agents)

with open(IN_PICKLE, 'rb') as f:
    all_data_sets = pickle.load(f)

n_of_other_sets = 0
comparison_df = pd.DataFrame()
for frozen_set_of_residential_building_agents, mock_data_frame in all_data_sets.items():
    if get_elec_cons_key(AGENT_TO_LOOK_AT) in mock_data_frame:
        if frozen_set_of_residential_building_agents == current_config_rbas:
            name_for_this_set_of_rbas = 'Current'
        else:
            n_of_other_sets = n_of_other_sets + 1
            name_for_this_set_of_rbas = 'Other' + str(n_of_other_sets)
        elec_cons_bc1 = mock_data_frame[get_elec_cons_key(AGENT_TO_LOOK_AT)]
        heat_cons_bc1 = mock_data_frame[get_heat_cons_key(AGENT_TO_LOOK_AT)]
        comparison_df[name_for_this_set_of_rbas + 'Elec'] = elec_cons_bc1
        comparison_df[name_for_this_set_of_rbas + 'Heat'] = heat_cons_bc1

comparison_df.to_csv('./agent_elec_cons.csv')
