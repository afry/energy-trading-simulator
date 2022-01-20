import pickle

IN_PICKLE = './tradingplatformpoc/data/generated/mock_datas_copy.pickle'
OUT_PICKLE = './tradingplatformpoc/data/generated/mock_datas.pickle'

with open(IN_PICKLE, 'rb') as f:
    all_data_sets = pickle.load(f)

new_data_sets = {}

for frozen_set_of_residential_building_agents, mock_data_frame in all_data_sets.items():
    if len(frozen_set_of_residential_building_agents) > 10:
        # Only keep big ones
        new_set_of_agents = set()
        for residential_building_agent_as_frozen_set in frozen_set_of_residential_building_agents:
            new_agent_dict = {}
            for item in residential_building_agent_as_frozen_set:
                if item[0] in ['Type', 'Name']:
                    new_agent_dict[item[0]] = 'Residential' + item[1]
                else:
                    new_agent_dict[item[0]] = item[1]
            new_set_of_agents.add(frozenset(new_agent_dict.items()))

        new_data_sets[frozenset(new_set_of_agents)] = mock_data_frame.add_prefix('Residential')
pickle.dump(new_data_sets, open(OUT_PICKLE, 'wb'))
