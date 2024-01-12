from typing import Any, Dict, Iterable

import streamlit as st

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.config.access_config import read_agent_defaults, read_agent_specs
from tradingplatformpoc.trading_platform_utils import ALL_AGENT_TYPES, ALL_IMPLEMENTED_RESOURCES_STR, get_if_exists_else


def remove_agent(some_agent: Dict[str, Any]):
    if some_agent['Type'] == 'GridAgent':
        st.error('Not allowed to remove GridAgent!')
    else:
        st.session_state.config_data['Agents'].remove(some_agent)


def duplicate_agent(some_agent: Dict[str, Any]):
    """
    Takes a copy of the input agent, modifies the name (making sure that no other agent has exactly that name), and adds
    it to the session_state list of agents.
    """
    new_agent = some_agent.copy()
    current_config = st.session_state.config_data
    all_agent_names = [agent['Name'] for agent in current_config['Agents']]
    n_copies_existing = 1
    while n_copies_existing:
        new_name = new_agent['Name'] + " copy " + str(n_copies_existing)
        if new_name not in all_agent_names:
            new_agent['Name'] = new_name
            break
        else:
            n_copies_existing += 1
    st.session_state.config_data['Agents'].append(new_agent)


def remove_all_building_agents():
    st.session_state.config_data['Agents'] = [agent for agent in st.session_state.config_data['Agents']
                                              if agent['Type'] != 'BuildingAgent']


def add_agent(new_agent: Dict[str, Any]):
    """
    Adding new agent to agents.
    Keeps track of how many agents have been added with the same prefix and names the new agent accordingly:
    The first will be named 'New[insert agent type]1', the second 'New[insert agent type]2' etc.
    """

    current_config = st.session_state.config_data
    name_str = "New" + new_agent['Type']
    number_of_existing_new_agents = len([agent for agent in current_config['Agents'] if name_str in agent['Name']])
    new_agent["Name"] = name_str + str(number_of_existing_new_agents + 1)
    agent_inputs(new_agent, new=True)


def add_building_agent():
    add_agent({
        "Type": "BuildingAgent",
        **read_agent_defaults("BuildingAgent", read_agent_specs())
    })


def add_battery_agent():
    add_agent({
        "Type": "BatteryAgent",
        **read_agent_defaults("BatteryAgent", read_agent_specs())
    })


def add_pv_agent():
    add_agent({
        "Type": "PVAgent",
        **read_agent_defaults("PVAgent", read_agent_specs())
    })


def add_grocery_store_agent():
    add_agent({
        "Type": "GroceryStoreAgent",
        **read_agent_defaults("GroceryStoreAgent", read_agent_specs())
    })


def agent_inputs(agent, new: bool = False):
    """Contains input fields needed to define an agent."""
    form = st.form(key="Form" + agent['Name'])

    # Name and agent type
    agent['Name'] = form.text_input('Name', key='NameField' + agent['Name'], value=agent['Name'])
    agent['Type'] = form.selectbox('Type', options=ALL_AGENT_TYPES,
                                   key='TypeSelectBox' + agent['Name'],
                                   index=ALL_AGENT_TYPES.index(agent['Type']))
    
    # Resource
    if agent['Type'] == 'GridAgent':
        agent['Resource'] = form.selectbox('Resource', options=ALL_IMPLEMENTED_RESOURCES_STR,
                                           key='ResourceSelectBox' + agent['Name'],
                                           index=ALL_IMPLEMENTED_RESOURCES_STR.index(agent['Resource']))

    # Parameters
    agent_specs = read_agent_specs()
    for key, val in agent_specs[agent['Type']].items():
        params = {k: v for k, v in val.items() if k not in
                  ['display', 'default_value', 'type', 'disabled_cond']}
        
        if 'disabled_cond' in val.keys():
            for k, v in val['disabled_cond'].items():
                params['disabled'] = (agent[k] == v)

        # Use default value if no other value is specified
        value = get_if_exists_else(agent, key, val['default_value'])

        if ("type", "float") in val.items():
            value = float(value)
        elif ("type", "int") in val.items():
            value = int(value)

        agent[key] = form.number_input(val["display"], **params, value=value,
                                       key=key + agent['Name'])
        
    # Submit
    submit = form.form_submit_button('Save agent')
    if submit:
        submit = False
        if new is True:
            st.session_state.config_data['Agents'].append(agent)
            # To keep track of if the success text should be displayed
            st.session_state.agents_added = True
        st.experimental_rerun()


def get_agent(all_agents: Iterable[IAgent], agent_chosen_guid: str) -> IAgent:
    return [x for x in all_agents if x.guid == agent_chosen_guid][0]
# -------------------------------------- End agent functions ----------------------------------


def add_params_to_form(form, param_spec_dict: dict, info_type: str):
    """Populate parameter forms. Will use radio buttons for booleans, number inputs for all others."""
    current_config = st.session_state.config_data
    bool_options = [True, False]
    for key, val in param_spec_dict[info_type].items():
        if isinstance(val['default'], bool):
            st.session_state.config_data[info_type][key] = form.radio(
                label=val['display'], help=val['help'],
                options=bool_options, index=bool_options.index(current_config[info_type][key]))
        else:
            params = {k: v for k, v in val.items() if k not in ['display', 'default']}
            st.session_state.config_data[info_type][key] = form.number_input(
                val['display'], **params,
                value=current_config[info_type][key])
