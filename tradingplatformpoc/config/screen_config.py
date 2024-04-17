# ---------------------------------------- Config screening -----------------------------------
from typing import Dict, List, Optional, Tuple

from tradingplatformpoc.config.access_config import read_agent_specs, read_param_specs
from tradingplatformpoc.trading_platform_utils import ALLOWED_GRID_AGENT_RESOURCES_STR


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
    """
    Check that config is structured as expected.
    Will return None if no problem is found.
    """
    # Make sure no unrecognized keys are passed
    un_req = [key for key in config_data.keys() if key not in ['Agents', 'AreaInfo', 'MockDataConstants']]
    if len(un_req) > 0:
        return 'Unrecognized key/keys: [\'{}\'] in uploaded config.'.format(', '.join(un_req))

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
    """
    Check that config json contains reasonable parameters.
    Will return None if no problem is found.
    """

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
                if "default" in param_specs[info_type][key].keys():
                    param_type = type(param_specs[info_type][key]['default'])
                    if not isinstance(val, param_type):
                        return "Provided value for {} should be of type {}!".format(key, param_type)
            else:
                return "Parameter {} is not a valid parameter.".format(key)
    return None


def config_data_agent_screening(config_data: dict) -> Optional[str]:
    """
    Check that config json contains reasonable agents.
    Will return None if no problem is found.
    """

    # Make sure no agents are passed without name or type
    for agent in config_data['Agents']:
        if 'Type' not in agent.keys():
            return 'Agent {} provided without \'Type\'.'.format(agent['Name'])
        if 'Name' not in agent.keys():
            return 'Agent of type {} provided without \'Name\'.'.format(agent['Type'])

    # Make sure no agents are passed with unknown type
    for agent in config_data['Agents']:
        if agent['Type'] not in ['BlockAgent', 'GridAgent', 'GroceryStoreAgent']:
            return 'Agent {} provided with unrecognized \'Type\' {}.'.format(agent['Name'], agent['Type'])

        # Check if resource is valid
        if agent['Type'] == 'GridAgent':
            if 'Resource' not in agent.keys():
                return "No specified resource for agent {}.".format(agent['Name'])

            if not agent['Resource'] in ALLOWED_GRID_AGENT_RESOURCES_STR:
                return "Resource {} is not in available for agent {}.".format(agent['Resource'], agent['Name'])

    # Needs exactly two GridAgents, one for each resource
    if 'GridAgent' not in [agent['Type'] for agent in config_data['Agents']]:
        return 'No GridAgent provided!'
    for resource in ALLOWED_GRID_AGENT_RESOURCES_STR:
        if resource not in [agent['Resource'] for agent in config_data['Agents'] if agent['Type'] == 'GridAgent']:
            return 'No GridAgent with resource: {} provided!'.format(resource)
    if (len([agent['Resource'] for agent in config_data['Agents'] if agent['Type'] == 'GridAgent'])
       > len(ALLOWED_GRID_AGENT_RESOURCES_STR)):
        return 'Too many GridAgents provided, should be one for each resource!'
    # Needs at least one other agent
    if len([agent for agent in config_data['Agents'] if agent['Type'] != 'GridAgent']) == 0:
        return 'No non-GridAgents provided, needs at least one other agent!'

    # Check agents for correct keys and values in ranges
    agent_specs = read_agent_specs()
    for agent in config_data['Agents']:
        items = {k: v for k, v in agent.items() if k not in ['Type', 'Name']}
        for key, val in items.items():

            if key not in agent_specs[agent['Type']].keys():
                return ("Specified {} not in available "
                        "input params for agent {} of type {}.".format(key, agent['Name'], agent['Type']))

            if "min_value" in agent_specs[agent['Type']][key].keys():
                if val < agent_specs[agent['Type']][key]["min_value"]:
                    return "Specified {}: {} < {}.".format(key, val, agent_specs[
                        agent['Type']][key]["min_value"])

            if "max_value" in agent_specs[agent['Type']][key].keys():
                if val > agent_specs[agent['Type']][key]["max_value"]:
                    return "Specified {}: {} > {}.".format(key, val, agent_specs[
                        agent['Type']][key]["max_value"])

        for key, val in agent_specs[agent['Type']].items():
            if key not in items.keys():
                if ('optional' not in val.keys()) or (not val['optional']):
                    return "Missing parameter {} for agent {}.".format(key, agent['Name'])

    return None


def config_data_feasibility_screening(config_data: dict) -> Optional[str]:
    """
    This function is intended to catch things that will lead to the optimization problem in CEMS_function.py being
    infeasible. This can be caused by stuff like it not being possible to generate enough of a certain resource, either
    in the LEC as a whole, or for a specific agent.
    It may be necessary to change this method if certain changes are made to field names in the config, or if
    certain constraints in CEMS_function.py are modified.

    @return: Will return None if no problem is found. Otherwise, will return a string describing the problem found.
    """
    area_info = config_data['AreaInfo']
    non_grid_agents_w_atemp = [agent for agent in config_data['Agents']
                               if agent['Type'] != 'GridAgent' and agent['Atemp'] > 0]

    # Check that cooling demand can be met
    has_cooling_need = any([agent['Type'] == 'BlockAgent'
                            and (agent['FractionCommercial'] + agent['FractionOffice'] > 0)
                            for agent in non_grid_agents_w_atemp])
    central_cool_prod = area_info['CompChillerMaxInput'] * area_info['CompChillerCOP'] * area_info['LocalMarketEnabled']
    worst_case_max_cool_prod_agent = [
        (min(area_info['COPHeatPumpsHighTemp'], area_info['COPHeatPumpsLowTemp']) - 1) * agent['HeatPumpMaxOutput']
        if agent['HeatPumpForCooling'] else 0
        for agent in non_grid_agents_w_atemp if agent['Type'] == 'BlockAgent']
    has_cooling_production = central_cool_prod > 0 or any([cp > 0 for cp in worst_case_max_cool_prod_agent])
    if has_cooling_need and not has_cooling_production:
        return 'The config includes agents with a cooling demand, but no ways of cooling production!'

    # Check that booster heat pumps exist
    has_hw_need = non_grid_agents_w_atemp
    has_booster_hp = [agent['BoosterPumpMaxOutput'] > 0 and agent['BoosterPumpMaxInput'] > 0
                      for agent in non_grid_agents_w_atemp]
    problem_agents = [non_grid_agents_w_atemp[i]['Name']
                      for i in range(len(has_hw_need))
                      if has_hw_need[i] and not has_booster_hp[i]]
    if len(problem_agents) > 0:
        if len(problem_agents) > 1:
            return 'Agents {} need booster heat pumps!'.format(problem_agents)
        return 'Agent {} needs a booster heat pump!'.format(problem_agents[0])
    return None
# ------------------------------------- End config screening ----------------------------------


# -------------------------------------- Start diff display -----------------------------------
def agent_diff(old: dict, new: dict) -> Tuple[List[str], List[str], Dict[str, dict]]:
    """Returns agents removed, agents added and params changed for agents."""
    agents_in_old = [agent['Name'] for agent in old['Agents']]
    agents_in_new = [agent['Name'] for agent in new['Agents']]

    agents_same = [x for x in agents_in_new if x in set(agents_in_old)]
    agents_only_in_old = [x for x in agents_in_old if x not in set(agents_same)]
    agents_only_in_new = [x for x in agents_in_new if x not in set(agents_same)]

    param_diff_dict = {}
    for agent_name in agents_same:
        agent_old = [agent for agent in old['Agents'] if agent['Name'] == agent_name][0]
        agent_new = [agent for agent in new['Agents'] if agent['Name'] == agent_name][0]
        diffs_for_agent = get_diffs_in_dict_with_same_keys(agent_old, agent_new)
        if len(diffs_for_agent) > 0:
            param_diff_dict[agent_name] = diffs_for_agent

    return agents_only_in_old, agents_only_in_new, param_diff_dict


def param_diff(old: dict, new: dict) -> Tuple[dict, dict]:
    """Returns lists of parameter key, pairs that differ between the two inputs."""
    area_info_diffs = get_diffs_in_dict_with_same_keys(old['AreaInfo'], new['AreaInfo'])
    mdc_diffs = get_diffs_in_dict_with_same_keys(old['MockDataConstants'], new['MockDataConstants'])
    return area_info_diffs, mdc_diffs


def get_diffs_in_dict_with_same_keys(old_dict: dict, new_dict: dict) -> dict:
    diff = set(old_dict.items()) - set(new_dict.items())
    if len(diff) > 0:
        return dict((key, {'old': old_dict[key],
                           'new': new_dict[key]}) for key in dict(diff).keys())
    return {}


def display_diff_in_config(old: dict, new: dict) -> List[str]:
    """Outputs list of strings displaying changes made to the config."""

    str_to_disp = []

    old_agents, new_agents, changes_to_agents = agent_diff(old.copy(), new.copy())

    if len(old_agents) > 0:
        str_to_disp.append('**Removed agents:** ')
        str_to_disp.append(', '.join(old_agents))
    if len(new_agents) > 0:
        str_to_disp.append('**Added agents:** ')
        str_to_disp.append(', '.join(new_agents))
    if len(changes_to_agents.keys()) > 0:
        str_to_disp.append('**Changes to agents:**')
        for name, params in changes_to_agents.items():
            str_agent_change = name + ': ' + '*'
            for key, vals in params.items():
                str_agent_change += diff_string(key, vals['old'], vals['new'])
            str_to_disp.append(str_agent_change[:-2] + '*')

    changes_to_area_info_params, changes_to_mock_data_params = param_diff(old.copy(), new.copy())

    if len(changes_to_area_info_params) > 0:
        str_to_disp.append('**Changes to area info parameters:**')
        str_area_info_change = ''
        for key, vals in changes_to_area_info_params.items():
            str_area_info_change += diff_string(key, vals['old'], vals['new'])
        str_to_disp.append(str_area_info_change[:-2])  # To remove the final ', '

    if len(changes_to_mock_data_params) > 0:
        str_to_disp.append('**Changes to mock data parameters:**')
        str_mdc_change = ''
        for key, vals in changes_to_mock_data_params.items():
            str_mdc_change += diff_string(key, vals['old'], vals['new'])
        str_to_disp.append(str_mdc_change[:-2])  # To remove the final ', '

    return str_to_disp


def diff_string(key: str, old_val: float, new_val: float) -> str:
    """
    Will output for example:
    Atemp: 11305 → 11315
    """
    return key + ': ' + str(round_if_float(old_val)) + ' &rarr; ' + str(round_if_float(new_val)) + ', '


def round_if_float(value):
    """Round floats, so that we avoid printing things like 0.0000000000001"""
    return round(value, 5) if isinstance(value, float) else value
# --------------------------------------- End diff display ------------------------------------
