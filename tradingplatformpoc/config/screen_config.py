# ---------------------------------------- Config screening -----------------------------------
from typing import Dict, List, Optional, Tuple

from tradingplatformpoc.config.access_config import read_agent_specs, read_param_specs
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES_STR


def config_data_json_screening(config_data: dict) -> Optional[str]:
    """
    This function was made to check the input parameters in the config json for reasonable values ONCE,
    at the beginning of running the simulation. This should ensure that all variables needed are present.
    """

    str1 = config_data_keys_screening(config_data)
    if str1 is not None:
        return str1
    str2 = config_data_param_screening(config_data)
    if str2 is not None:
        return str2
    str3 = config_data_agent_screening(config_data)
    if str3 is not None:
        return str3
    return None


def config_data_keys_screening(config_data: dict) -> Optional[str]:
    """Check that config is structured as expected."""
    # Make sure no unrecognized keys are passed
    unreq = [key for key in config_data.keys() if key not in ['Agents', 'AreaInfo', 'MockDataConstants']]
    if len(unreq) > 0:
        return 'Unrecognized key/keys: [\'{}\'] in uploaded config.'.format(', '.join(unreq))
    
    if 'AreaInfo' in config_data:
        if not isinstance(config_data['AreaInfo'], dict):
            return '\'AreaInfo\'should be provided as a dict.'

    if 'MockDataConstants' in config_data:
        if not isinstance(config_data['MockDataConstants'], dict):
            return '\'MockDataConstants\' should be provided as a dict.'
        
    # Make sure agents are provided as list
    if 'Agents' not in config_data:
        return 'No agents are provided!'

    if not isinstance(config_data['Agents'], list):
        return '\'Agents\' values should be provided as a list.'

    if len(config_data['Agents']) == 0:
        return 'No agents are provided!'

    return None


def config_data_param_screening(config_data: dict) -> Optional[str]:
    """Check that config json contains reasonable parameters."""

    param_specs = read_param_specs(['AreaInfo', 'MockDataConstants'])

    # Check params for correct keys and values in ranges
    for info_type in [c for c in ['AreaInfo', 'MockDataConstants'] if c in config_data]:
        for key, val in config_data[info_type].items():
            if key in param_specs[info_type].keys():

                if "min_value" in param_specs[info_type][key].keys():
                    if val < param_specs[info_type][key]["min_value"]:
                        return "Specified {}: {} < {}.".format(key, val, param_specs[
                            info_type][key]["min_value"])
                if "max_value" in param_specs[info_type][key].keys():
                    if val > param_specs[info_type][key]["max_value"]:
                        return "Specified {}: {} > {}.".format(key, val, param_specs[
                            info_type][key]["max_value"])
            else:
                return "Parameter {} is not a valid parameter.".format(key)
    return None


def config_data_agent_screening(config_data: dict) -> Optional[str]:
    """Check that config json contains reasonable agents."""

    # Make sure no agents are passed without name or type
    for agent in config_data['Agents']:
        if 'Type' not in agent.keys():
            return 'Agent {} provided without \'Type\'.'.format(agent['Name'])
        if 'Name' not in agent.keys():
            return 'Agent of type {} provided without \'Name\'.'.format(agent['Type'])

    # Make sure no agents are passed with unknown type
    for agent in config_data['Agents']:
        if agent['Type'] not in ['BuildingAgent', 'StorageAgent', 'PVAgent', 'GridAgent', 'GroceryStoreAgent']:
            return 'Agent {} provided with unrecognized \'Type\' {}.'.format(agent['Name'], agent['Type'])
        
        # Check if resource is valid
        if agent['Type'] in ['StorageAgent', 'GridAgent']:
            if 'Resource' not in agent.keys():
                return "No specified resource for agent {}.".format(agent['Name'])

            if not agent['Resource'] in ALL_IMPLEMENTED_RESOURCES_STR:
                return "Resource {} is not in availible for agent {}.".format(agent['Resource'], agent['Name'])
            
            # TODO: This can be removed when heating is implemented for StorageAgent
            if agent['Type'] == 'StorageAgent':
                if not agent['Resource'] == 'ELECTRICITY':
                    return "Resource {} is not yet availible for agent {}.".format(agent['Resource'], agent['Name'])
        
    # Needs exactly two GridAgents, one for each resource
    if 'GridAgent' not in [agent['Type'] for agent in config_data['Agents']]:
        return 'No GridAgent provided!'
    for resource in ALL_IMPLEMENTED_RESOURCES_STR:
        if resource not in [agent['Resource'] for agent in config_data['Agents'] if agent['Type'] == 'GridAgent']:
            return 'No GridAgent with resource: {} provided!'.format(resource)
    if (len([agent['Resource'] for agent in config_data['Agents'] if agent['Type'] == 'GridAgent'])
       > len(ALL_IMPLEMENTED_RESOURCES_STR)):
        return 'Too many GridAgents provided, should be one for each resource!'
    # Needs at least one other agent
    if len([agent for agent in config_data['Agents'] if agent['Type'] != 'GridAgent']) == 0:
        return 'No non-GridAgents provided, needs at least one other agent!'
    # TODO: Should we allow for having no BuildingAgents?
    
    # Check agents for correct keys and values in ranges
    agent_specs = read_agent_specs()
    for agent in config_data['Agents']:
        items = {k: v for k, v in agent.items() if k not in ['Type', 'Name', 'Resource']}
        for key, val in items.items():

            if key not in agent_specs[agent['Type']].keys():
                return ("Specified {} not in availible "
                        "input params for agent {} of type {}.".format(key, agent['Name'], agent['Type']))
            
            if "min_value" in agent_specs[agent['Type']][key].keys():
                if val < agent_specs[agent['Type']][key]["min_value"]:
                    return "Specified {}: {} < {}.".format(key, val, agent_specs[
                        agent['Type']][key]["min_value"])
                
            if "max_value" in agent_specs[agent['Type']][key].keys():
                if val > agent_specs[agent['Type']][key]["max_value"]:
                    return "Specified {}: {} > {}.".format(key, val, agent_specs[
                        agent['Type']][key]["max_value"])
            
        for key in [key for key, val in agent_specs[agent['Type']].items()]:
            if key not in items.keys():
                return "Missing parameter {} for agent {}.".format(key, agent['Name'])

    return None
# ------------------------------------- End config screening ----------------------------------


# -------------------------------------- Start diff display -----------------------------------
def agent_diff(default: dict, new: dict) -> Tuple[List[str], List[str], Dict[str, dict]]:
    """Returns agents removed, agents added and paramas changed for agents."""
    agents_in_default = [agent['Name'] for agent in default['Agents']]
    agents_in_new = [agent['Name'] for agent in new['Agents']]

    agents_same = [x for x in agents_in_new if x in set(agents_in_default)]
    agents_only_in_default = [x for x in agents_in_default if x not in set(agents_same)]
    agents_only_in_new = [x for x in agents_in_new if x not in set(agents_same)]

    param_diff = {}
    for agent_name in agents_same:
        agent_default = [agent for agent in default['Agents'] if agent['Name'] == agent_name][0]
        agent_new = [agent for agent in new['Agents'] if agent['Name'] == agent_name][0]
        diff = set(agent_default.items()) - set(agent_new.items())
        if len(diff) > 0:
            param_diff[agent_name] = dict((key, {'default': agent_default[key],
                                                 'new': agent_new[key]}) for key in dict(diff).keys())

    return agents_only_in_default, agents_only_in_new, param_diff


def param_diff(default: dict, new: dict) -> Tuple[List[Tuple], List[Tuple]]:
    """Returns lists of parameter key, pairs that differ from the default."""
    changed_area_info_params = list(set(default['AreaInfo'].items()) - set(new['AreaInfo'].items()))
    changed_mock_data_params = list(set(default['MockDataConstants'].items()) - set(new['MockDataConstants'].items()))
    return changed_area_info_params, changed_mock_data_params


def display_diff_in_config(default: dict, new: dict) -> List[str]:
    """Outputs list of strings displaying changes made to the config."""

    str_to_disp = []

    old_agents, new_agents, changes_to_agents = agent_diff(default.copy(), new.copy())

    if len(old_agents) > 0:
        str_to_disp.append('**Removed agents:** ')
        str_to_disp.append(', '.join(old_agents))
    if len(new_agents) > 0:
        str_to_disp.append('**Added agents:** ')
        str_to_disp.append(', '.join(new_agents))
    if len(changes_to_agents.keys()) > 0:
        str_to_disp.append('**Changes to default agents:**')
        for name, params in changes_to_agents.items():
            str_agent_change = name + ': ' + '*'
            for key, vals in params.items():
                str_agent_change += (key + ': ' + str(vals['default']) + ' &rarr; '
                                     + str(vals['new']) + ', ')
            str_to_disp.append(str_agent_change[:-2] + '*')

    changes_to_area_info_params, changes_to_mock_data_params = param_diff(default.copy(), new.copy())

    if len(changes_to_area_info_params) > 0:
        str_to_disp.append('**Changes to area info parameters:**')
        for param in changes_to_area_info_params:
            str_to_disp.append(param[0] + ': ' + str(param[1]))

    if len(changes_to_mock_data_params) > 0:
        str_to_disp.append('**Changes to mock data parameters:**')
        for param in changes_to_mock_data_params:
            str_to_disp.append(param[0] + ': ' + str(param[1]))

    return str_to_disp
# --------------------------------------- End diff display ------------------------------------


def compare_pv_efficiency(config: dict) -> str:
    """If the PVEfficiency of agents differs from default, return message."""
    agents_w_pv_eff = [agent for agent in config['Agents'] if 'PVEfficiency' in agent.keys()]
    agentw_w_other_pv_eff = [agent['Name'] for agent in agents_w_pv_eff if
                             agent['PVEfficiency'] != config['AreaInfo']['DefaultPVEfficiency']]
    if len(agentw_w_other_pv_eff) > 0:
        return "PV efficiency differs from default for {}".format(', '.join(agentw_w_other_pv_eff))
    return None
