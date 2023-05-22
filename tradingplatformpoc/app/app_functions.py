import datetime
import json
import os
import pickle
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import altair as alt

import pandas as pd

from pkg_resources import resource_filename

import streamlit as st

from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.app import app_constants
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.generate_mock_data import create_inputs_df
from tradingplatformpoc.results.results_key import ResultsKey
from tradingplatformpoc.results.simulation_results import SimulationResults
from tradingplatformpoc.trading_platform_utils import ALL_AGENT_TYPES, ALL_IMPLEMENTED_RESOURCES_STR, get_if_exists_else


def get_price_df_when_local_price_inbetween(prices_df: pd.DataFrame, resource: Resource) -> pd.DataFrame:
    """Local price is almost always either equal to the external wholesale or retail price. This method returns the
    subsection of the prices dataframe where the local price is _not_ equal to either of these two."""
    elec_prices = prices_df. \
        loc[prices_df['Resource'].apply(lambda x: x.name) == resource.name]. \
        drop('Resource', axis=1). \
        pivot(index="period", columns="variable")['value']
    local_price_between_external = (elec_prices[app_constants.LOCAL_PRICE_STR]
                                    > elec_prices[app_constants.WHOLESALE_PRICE_STR]
                                    + 0.0001) & (elec_prices[app_constants.LOCAL_PRICE_STR]
                                                 < elec_prices[app_constants.RETAIL_PRICE_STR] - 0.0001)
    return elec_prices.loc[local_price_between_external]


def construct_price_chart(prices_df: pd.DataFrame, resource: Resource) -> alt.Chart:
    data_to_use = prices_df.loc[prices_df['Resource'] == resource].drop('Resource', axis=1)
    domain = [app_constants.LOCAL_PRICE_STR, app_constants.RETAIL_PRICE_STR, app_constants.WHOLESALE_PRICE_STR]
    range_color = ['blue', 'green', 'red']
    range_dash = [[0, 0], [2, 4], [2, 4]]
    return alt.Chart(data_to_use).mark_line(). \
        encode(x=alt.X('period', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
               y=alt.Y('value', axis=alt.Axis(title='Price [SEK]')),
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               strokeDash=alt.StrokeDash('variable', scale=alt.Scale(domain=domain, range=range_dash)),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='variable', title='Variable'),
                        alt.Tooltip(field='value', title='Value')]). \
        interactive(bind_y=False)


def construct_static_digital_twin_chart(digital_twin: StaticDigitalTwin, should_add_hp_to_legend: bool = False) -> \
        alt.Chart:
    """
    Constructs a multi-line chart from a StaticDigitalTwin, containing all data held therein.
    """
    df = pd.DataFrame()
    # Defining colors manually, so that for example heat consumption has the same color for every agent, even if for
    # example electricity production doesn't exist for one of them.
    domain = []
    range_color = []
    if digital_twin.electricity_production is not None:
        df = pd.concat((df, pd.DataFrame({'period': digital_twin.electricity_production.index,
                                          'value': digital_twin.electricity_production.values,
                                          'variable': app_constants.ELEC_PROD})))
        domain.append(app_constants.ELEC_PROD)
        range_color.append(app_constants.ALTAIR_BASE_COLORS[0])
    if digital_twin.electricity_usage is not None:
        df = pd.concat((df, pd.DataFrame({'period': digital_twin.electricity_usage.index,
                                          'value': digital_twin.electricity_usage.values,
                                          'variable': app_constants.ELEC_CONS})))
        domain.append(app_constants.ELEC_CONS)
        range_color.append(app_constants.ALTAIR_BASE_COLORS[1])
    if digital_twin.heating_production is not None:
        df = pd.concat((df, pd.DataFrame({'period': digital_twin.heating_production.index,
                                          'value': digital_twin.heating_production.values,
                                          'variable': app_constants.HEAT_PROD})))
        domain.append(app_constants.HEAT_PROD)
        range_color.append(app_constants.ALTAIR_BASE_COLORS[2])
    if digital_twin.heating_usage is not None:
        df = pd.concat((df, pd.DataFrame({'period': digital_twin.heating_usage.index,
                                          'value': digital_twin.heating_usage.values,
                                          'variable': app_constants.HEAT_CONS})))
        domain.append(app_constants.HEAT_CONS)
        range_color.append(app_constants.ALTAIR_BASE_COLORS[3])
    if should_add_hp_to_legend:
        domain.append('Heat pump workload')
        range_color.append(app_constants.HEAT_PUMP_CHART_COLOR)
    return altair_period_chart(df, domain, range_color)


def construct_building_with_heat_pump_chart(agent_chosen: Union[BuildingAgent, PVAgent],
                                            heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]]) -> \
        alt.Chart:
    """
    Constructs a multi-line chart with energy production/consumption levels, with any heat pump workload data in the
    background. If there is no heat_pump_data, will just return construct_static_digital_twin_chart(digital_twin).
    """

    heat_pump_data = heat_pump_levels_dict.get(agent_chosen.guid, {})
    if heat_pump_data == {}:
        return construct_static_digital_twin_chart(agent_chosen.digital_twin, False)

    st.write('Note: Energy production/consumption values do not include production/consumption by the heat pumps.')
    heat_pump_df = pd.DataFrame.from_dict(heat_pump_data, orient='index').reset_index()
    heat_pump_df.columns = ['period', 'Heat pump workload']
    heat_pump_area = alt.Chart(heat_pump_df). \
        mark_area(color=app_constants.HEAT_PUMP_CHART_COLOR, opacity=0.3, interpolate='step-after'). \
        encode(
        x=alt.X('period:T', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
        y=alt.Y('Heat pump workload', axis=alt.Axis(title='Heat pump workload', titleColor='gray')),
        tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                 alt.Tooltip(field='Heat pump workload', title='Heat pump workload', type='quantitative')]
    )

    energy_multiline = construct_static_digital_twin_chart(agent_chosen.digital_twin, True)
    return alt.layer(heat_pump_area, energy_multiline).resolve_scale(y='independent')


def construct_storage_level_chart(storage_levels_dict: Dict[datetime.datetime, float]) -> alt.Chart:
    storage_levels = pd.DataFrame.from_dict(storage_levels_dict, orient='index').reset_index()
    storage_levels.columns = ['period', 'capacity_kwh']
    return alt.Chart(storage_levels).mark_line(). \
        encode(x=alt.X('period', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
               y=alt.Y('capacity_kwh', axis=alt.Axis(title='Capacity [kWh]')),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='capacity_kwh', title='Capacity [kWh]')]). \
        interactive(bind_y=False)


def construct_prices_df(simulation_results: SimulationResults) -> pd.DataFrame:
    """Constructs a pandas DataFrame on the format which fits Altair, which we use for plots."""
    clearing_prices_df = pd.DataFrame.from_dict(simulation_results.clearing_prices_historical, orient='index')
    clearing_prices_df.index.set_names('period', inplace=True)
    clearing_prices_df = clearing_prices_df.reset_index().melt('period')
    clearing_prices_df['Resource'] = clearing_prices_df['variable']
    clearing_prices_df.variable = app_constants.LOCAL_PRICE_STR

    data_store_entity = simulation_results.data_store
    nordpool_data = data_store_entity.nordpool_data
    nordpool_data.name = 'value'
    nordpool_data = nordpool_data.to_frame().reset_index()
    nordpool_data['Resource'] = Resource.ELECTRICITY
    nordpool_data.rename({'datetime': 'period'}, axis=1, inplace=True)
    nordpool_data['period'] = pd.to_datetime(nordpool_data['period'])
    retail_df = nordpool_data.copy()
    gross_prices = data_store_entity.get_electricity_gross_retail_price_from_nordpool_price(retail_df['value'])
    retail_df['value'] = data_store_entity.get_electricity_net_external_price(gross_prices)
    retail_df['variable'] = app_constants.RETAIL_PRICE_STR
    wholesale_df = nordpool_data.copy()
    wholesale_df['value'] = data_store_entity.get_electricity_wholesale_price_from_nordpool_price(wholesale_df['value'])
    wholesale_df['variable'] = app_constants.WHOLESALE_PRICE_STR
    return pd.concat([clearing_prices_df, retail_df, wholesale_df])


# @st.cache_data
def get_viewable_df(full_df: pd.DataFrame, key: str, value: Any, want_index: str,
                    cols_to_drop: Union[None, List[str]] = None) -> pd.DataFrame:
    """
    Will filter on the given key-value pair, drop the key and cols_to_drop columns, set want_index as index, and
    finally transform all Enums so that only their name is kept (i.e. 'Action.BUY' becomes 'BUY', which Streamlit can
    serialize.
    """
    if cols_to_drop is None:
        cols_to_drop = []
    cols_to_drop.append(key)
    return full_df. \
        loc[full_df[key] == value]. \
        drop(cols_to_drop, axis=1). \
        set_index([want_index]). \
        apply(lambda x: x.apply(lambda y: y.name) if isinstance(x.iloc[0], Enum) else x)


def results_dict_to_df(raw_dict: Dict[ResultsKey, float]) -> pd.DataFrame:
    """Converts the ResultsKey keys to strings, and then the dict to a pd.DataFrame since Streamlit likes that."""
    df = pd.DataFrame.from_dict({k.value: v for (k, v) in raw_dict.items()}, orient='index')
    df.rename({0: 'Value'}, axis=1, inplace=True)
    formatted_df = df.style.format({'Value': '{:.2f}'.format})
    return formatted_df


# -------------------------------------- Config functions -------------------------------------
def set_config(config: dict):
    """Writes config to current configuration file."""
    with open(app_constants.CURRENT_CONFIG_FILENAME, 'w') as f:
        json.dump(config, f)


def set_config_to_sess_state():
    """Writes session state config to current configuration file."""
    set_config(st.session_state.config_data)


def read_config(name: str = 'current') -> dict:
    """Reads and returns specified config from file."""
    file_dict = {'current': app_constants.CURRENT_CONFIG_FILENAME,
                 'default': app_constants.DEFAULT_CONFIG_FILENAME}

    with open(file_dict[name], "r") as jsonfile:
        config = json.load(jsonfile)
    return config


def reset_config():
    """Reads default configuration from file and writes to current configuration file."""
    config = read_config(name='default')
    set_config(config)


def get_config(reset: bool) -> dict:
    """
    If no current config file exists or the reset button is clicked, reset.
    Return current config.
    """
    if not os.path.exists(app_constants.CURRENT_CONFIG_FILENAME):
        reset_config()
        st.markdown("**Current configuration: :blue[DEFAULT]**")
    elif reset:
        reset = False
        reset_config()
        st.markdown("**Current configuration: :blue[DEFAULT]**")
    else:
        st.markdown("**Current configuration: :blue[LAST SAVED]**")
    config = read_config()
    return config


def fill_with_default_params(new_config: dict) -> dict:
    """If not all parameters are specified in uploaded config, use default for the unspecified ones."""
    default_config = read_config(name='default')
    for param_type in ['AreaInfo', 'MockDataConstants']:
        params_only_in_default = dict((k, v) for k, v in default_config[param_type].items()
                                      if k not in set(new_config[param_type].keys()))
        for k, v in params_only_in_default.items():
            new_config[param_type][k] = v
    return new_config
# ------------------------------------- End config functions ----------------------------------


# ------------------------------------- Save result functions ---------------------------------
def set_simulation_results(simulation_results: SimulationResults):
    """Writes simulation results to file."""

    data = (datetime.datetime.now(datetime.timezone.utc), simulation_results)
    with open(app_constants.LAST_SIMULATION_RESULTS, 'wb') as f:
        pickle.dump(data, f)


def read_simulation_results() -> Tuple[datetime.datetime, SimulationResults]:
    """Reads simulation results from file."""
    with open(app_constants.LAST_SIMULATION_RESULTS, 'rb') as f:
        res = pickle.load(f)
        (timestamp, simulation_results) = res
    return timestamp, simulation_results
# ----------------------------------- End save result functions -------------------------------


# ---------------------------------------- Agent functions ------------------------------------
def remove_agent(some_agent: Dict[str, Any]):
    if some_agent['Type'] == 'GridAgent':
        st.error('Not allowed to remove GridAgent!')
    else:
        st.session_state.config_data['Agents'].remove(some_agent)
        set_config_to_sess_state()


def duplicate_agent(some_agent: Dict[str, Any]):
    """
    Takes a copy of the input agent, modifies the name (making sure that no other agent has exactly that name), and adds
    it to the session_state list of agents.
    """
    new_agent = some_agent.copy()
    current_config = read_config()
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
    set_config_to_sess_state()


def remove_all_building_agents():
    st.session_state.config_data['Agents'] = [agent for agent in st.session_state.config_data['Agents']
                                              if agent['Type'] != 'BuildingAgent']
    set_config_to_sess_state()


def add_agent(new_agent: Dict[str, Any]):
    """
    Adding new agent to agents.
    Keeps track of how many agents have been added with the same prefix and names the new agent accordingly:
    The first will be named 'New[insert agent type]1', the second 'New[insert agent type]2' etc.
    """

    # To keep track of if the success text should be displayed
    st.session_state.agents_added = True

    current_config = read_config()
    name_str = "New" + new_agent['Type']
    number_of_existing_new_agents = len([agent for agent in current_config['Agents'] if name_str in agent['Name']])
    new_agent["Name"] = name_str + str(number_of_existing_new_agents + 1)
    st.session_state.config_data['Agents'].append(new_agent)
    set_config_to_sess_state()


def add_building_agent():
    add_agent({
        "Type": "BuildingAgent",
        "GrossFloorArea": 1000.0
    })
    set_config_to_sess_state()


def add_storage_agent():
    add_agent({
        "Type": "StorageAgent",
        "Resource": "ELECTRICITY",
        "Capacity": 1000,
        "ChargeRate": 0.4,
        "RoundTripEfficiency": 0.93,
        "NHoursBack": 168,
        "BuyPricePercentile": 20,
        "SellPricePercentile": 80
    })
    set_config_to_sess_state()


def add_pv_agent():
    add_agent({
        "Type": "PVAgent",
        "PVArea": 100
    })
    set_config_to_sess_state()


def add_grocery_store_agent():
    add_agent({
        "Type": "GroceryStoreAgent",
        "PVArea": 320
    })
    set_config_to_sess_state()


def add_grid_agent():
    add_agent({
        "Type": "GridAgent",
        "Resource": "ELECTRICITY",
        "TransferRate": 10000
    })
    set_config_to_sess_state()


def agent_inputs(agent):
    """Contains input fields needed to define an agent."""
    current_config = read_config()
    form = st.form(key="Form" + agent['Name'])
    agent['Name'] = form.text_input('Name', key='NameField' + agent['Name'], value=agent['Name'])
    agent['Type'] = form.selectbox('Type', options=ALL_AGENT_TYPES,
                                   key='TypeSelectBox' + agent['Name'],
                                   index=ALL_AGENT_TYPES.index(agent['Type']))
    
    if agent['Type'] == 'GridAgent':
        agent['Resource'] = form.selectbox('Resource', options=ALL_IMPLEMENTED_RESOURCES_STR,
                                           key='ResourceSelectBox' + agent['Name'],
                                           index=ALL_IMPLEMENTED_RESOURCES_STR.index(agent['Resource']))
    elif agent['Type'] == 'StorageAgent':
        # TODO: options should be ALL_IMPLEMENTED_RESOURCES_STR when HEATING is implemented for StorageAgent
        agent['Resource'] = form.selectbox('Resource', options=['ELECTRICITY'],
                                           key='ResourceSelectBox' + agent['Name'],
                                           index=['ELECTRICITY'].index(agent['Resource']))

    for key, val in app_constants.agent_specs_dict[agent['Type']].items():
        params = {k: v for k, v in val.items() if k not in
                  ['display', 'default_value', 'type', 'disabled_cond', 'required']}
        if 'disabled_cond' in val.keys():
            for k, v in val['disabled_cond'].items():
                params['disabled'] = (agent[k] == v)
        if key == "PVEfficiency":
            val['default_value'] = current_config['AreaInfo']['DefaultPVEfficiency']
        elif key == "DischargeRate":
            val['default_value'] = agent['ChargeRate']
        if 'default_value' in val.keys():
            value = get_if_exists_else(agent, key, val['default_value'])
        else:
            value = agent[key]
        if 'type' in val.keys():
            value = val['type'](value)

        agent[key] = form.number_input(val["display"], **params, value=value,
                                       key=key + agent['Name'])

    col1, col2 = st.columns(2)
    with col1:
        st.button('Remove agent', key='RemoveButton' + agent['Name'], on_click=remove_agent, args=(agent,),
                  use_container_width=True)
    with col2:
        st.button('Duplicate agent', key='DuplicateButton' + agent['Name'], on_click=duplicate_agent, args=(agent,),
                  use_container_width=True)
    submit = form.form_submit_button('Save agent')
    if submit:
        submit = False
        set_config_to_sess_state()
        st.experimental_rerun()


def get_agent(all_agents: Iterable[IAgent], agent_chosen_guid: str) -> IAgent:
    return [x for x in all_agents if x.guid == agent_chosen_guid][0]
# -------------------------------------- End agent functions ----------------------------------


def add_params_to_form(form, info_type: str):
    """Populate parameter forms."""
    current_config = read_config()
    for key, val in app_constants.param_spec_dict[info_type].items():
        params = {k: v for k, v in val.items() if k not in ['display', 'required']}
        st.session_state.config_data[info_type][key] = form.number_input(
            val['display'], **params,
            value=current_config[info_type][key])


# ---------------------------------------- Config screening -----------------------------------
def config_data_json_screening(config_data: dict) -> Optional[str]:
    """Check that config json contains reasonable inputs."""

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

    # Check params for correct keys and values in ranges
    for info_type in [c for c in ['AreaInfo', 'MockDataConstants'] if c in config_data]:
        for key, val in config_data[info_type].items():
            if key in app_constants.param_spec_dict[info_type].keys():

                if "min_value" in app_constants.param_spec_dict[info_type][key].keys():
                    if val < app_constants.param_spec_dict[info_type][key]["min_value"]:
                        return "Specified {}: {} < {}.".format(key, val, app_constants.param_spec_dict[
                            info_type][key]["min_value"])
                if "max_value" in app_constants.param_spec_dict[info_type][key].keys():
                    if val > app_constants.param_spec_dict[info_type][key]["max_value"]:
                        return "Specified {}: {} > {}.".format(key, val, app_constants.param_spec_dict[
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
        
    # Ensure all essential agents exists, and of the right amount.
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
    for agent in config_data['Agents']:
        items = {k: v for k, v in agent.items() if k not in ['Type', 'Name', 'Resource']}
        for key, val in items.items():

            if key not in app_constants.agent_specs_dict[agent['Type']].keys():
                return ("Specified {} not in availible "
                        "input params for agent {} of type {}.".format(key, agent['Name'], agent['Type']))
            
            if "min_value" in app_constants.agent_specs_dict[agent['Type']][key].keys():
                if val < app_constants.agent_specs_dict[agent['Type']][key]["min_value"]:
                    return "Specified {}: {} < {}.".format(key, val, app_constants.agent_specs_dict[
                        agent['Type']][key]["min_value"])
                
            if "max_value" in app_constants.agent_specs_dict[agent['Type']][key].keys():
                if val > app_constants.agent_specs_dict[agent['Type']][key]["max_value"]:
                    return "Specified {}: {} > {}.".format(key, val, app_constants.agent_specs_dict[
                        agent['Type']][key]["max_value"])
            
        for key in [key for key, val in app_constants.agent_specs_dict[agent['Type']].items() if val['required']]:
            if key not in items.keys():
                return "Missing parameter {} for agent {}.".format(key, agent['Name'])

    return None
# ------------------------------------- End config screening ----------------------------------


def set_max_width(width: str):
    """
    Sets the max width of the page. The input can be specified either in pixels (i.e. "500px") or as a percentage (i.e.
    "50%").
    Taken from https://discuss.streamlit.io/t/where-to-set-page-width-when-set-into-non-widescreeen-mode/959/16.
    """
    st.markdown(f"""
    <style>
    .appview-container .main .block-container{{ max-width: {width}; }}
    </style>
    """, unsafe_allow_html=True, )


def aggregated_taxes_and_fees_results_df() -> pd.DataFrame:
    """
    @return: Dataframe displaying total taxes and fees extracted from simulation results.
    """
    return pd.DataFrame(index=["Taxes paid on internal trades", "Grid fees paid on internal trades"],
                        columns=['Total'],
                        data=["{:.2f} SEK".format(st.session_state.simulation_results.tax_paid),
                              "{:.2f} SEK".format(st.session_state.simulation_results.grid_fees_paid_on_internal_trades)
                              ])


def get_total_import_export(resource: Resource, action: Action,
                            mask: Optional[pd.DataFrame] = None) -> float:
    """
    Extract total amount of resource imported to or exported from local market.
    @param resource: A member of Resource enum specifying which resource
    @param action: A member of Action enum specifying which action
    @param mask: Optional dataframe, if specified used to extract subset of trades
    @return: Total quantity post loss as float
    """
    conditions = (st.session_state.simulation_results.all_trades.by_external
                  & (st.session_state.simulation_results.all_trades.resource.values == resource)
                  & (st.session_state.simulation_results.all_trades.action.values == action))
    if mask is not None:
        conditions = (conditions & mask)

    return st.session_state.simulation_results.all_trades.loc[conditions].quantity_post_loss.sum()


def aggregated_import_and_export_results_df_split_on_mask(mask: pd.DataFrame,
                                                          mask_colnames: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Display total import and export for electricity and heat, computed for specified subsets.
    @param mask: Dataframe used to extract subset of trades
    @param mask_colnames: List with strings to display as subset names
    @return: Dict of dataframes displaying total import and export of resources split by the mask
    """

    rows = {'Electricity': Resource.ELECTRICITY, 'Heating': Resource.HEATING}
    cols = {'Imported': Action.SELL, 'Exported': Action.BUY}

    res_dict = {}
    for colname, action in cols.items():
        subdict = {'# trades': {mask_colnames[0]: "{:}".format(sum(mask)),
                                mask_colnames[1]: "{:}".format(sum(~mask)),
                                'Total': "{:}".format(len(mask))}}
        for rowname, resource in rows.items():
            w_mask = "{:.2f} MWh".format(get_total_import_export(resource, action, mask) / 10**3)
            w_compl_mask = "{:.2f} MWh".format(get_total_import_export(resource, action, ~mask) / 10**3)
            total = "{:.2f} MWh".format(get_total_import_export(resource, action) / 10**3)
            subdict[rowname] = {mask_colnames[0]: w_mask, mask_colnames[1]: w_compl_mask, 'Total': total}
        res_dict[colname] = pd.DataFrame.from_dict(subdict, orient='index')

    return res_dict


def aggregated_import_and_export_results_df_split_on_period() -> Dict[str, pd.DataFrame]:
    """
    Dict of dataframes displaying total import and export of resources split for January and
    February against rest of the year.
    """

    jan_feb_mask = st.session_state.simulation_results.all_trades.period.dt.month.isin([1, 2])

    return aggregated_import_and_export_results_df_split_on_mask(jan_feb_mask, ['Jan-Feb', 'Mar-Dec'])


def aggregated_import_and_export_results_df_split_on_temperature() -> Dict[str, pd.DataFrame]:
    """
    Dict of dataframes displaying total import and export of resources split for when the temperature was above
    or below 1 degree Celsius.
    """
    # Read in-data: Temperature and timestamps, TODO: simplify
    df_inputs, df_irrd = create_inputs_df(resource_filename(app_constants.DATA_PATH, 'temperature_vetelangden.csv'),
                                          resource_filename(app_constants.DATA_PATH, 'varberg_irradiation_W_m2_h.csv'),
                                          resource_filename(app_constants.DATA_PATH, 'vetelangden_slim.csv'))
    
    temperature_df = df_inputs.to_pandas()[['datetime', 'temperature']]
    temperature_df['above_1_degree'] = temperature_df['temperature'] >= 1.0

    period = st.session_state.simulation_results.all_trades.period
    temp_mask = pd.DataFrame(period).rename(columns={'period': 'datetime'}).merge(temperature_df, on='datetime',
                                                                                  how='left')['above_1_degree']
    return aggregated_import_and_export_results_df_split_on_mask(temp_mask, ['Above', 'Below'])


def aggregated_import_and_export_results_df() -> pd.DataFrame:
    """
    Display total import and export for electricity and heat.
    @return: Dataframe displaying total import and export of resources
    """
    rows = {'Electricity': Resource.ELECTRICITY, 'Heating': Resource.HEATING}
    cols = {'Imported': Action.SELL, 'Exported': Action.BUY}

    res_dict = {}
    for colname, action in cols.items():
        subdict = {}
        for rowname, resource in rows.items():
            subdict[rowname] = "{:.2f} kWh".format(get_total_import_export(resource, action))
        res_dict[colname] = subdict

    return pd.DataFrame.from_dict(res_dict)


def aggregated_local_production_df() -> pd.DataFrame:
    """
    Computing total amount of locally produced resources.
    """

    production_electricity_lst = []
    usage_heating_lst = []
    for agent in st.session_state.simulation_results.agents:
        if isinstance(agent, BuildingAgent) or isinstance(agent, PVAgent):
            production_electricity_lst.append(sum(agent.digital_twin.electricity_production))
    
    production_electricity = sum(production_electricity_lst)

    for agent in st.session_state.simulation_results.agents:
        if isinstance(agent, BuildingAgent):
            usage_heating_lst.append(sum(agent.digital_twin.heating_usage.dropna()))  # Issue with NaNs

    production_heating = (sum(usage_heating_lst) - get_total_import_export(Resource.HEATING, Action.BUY)
                          + get_total_import_export(Resource.HEATING, Action.SELL))

    data = [["{:.2f} MWh".format(production_electricity / 10**3)], ["{:.2f} MWh".format(production_heating / 10**3)]]
    return pd.DataFrame(data=data, index=['Electricity', 'Heating'], columns=['Total'])


# @st.cache_data
def results_by_agent_as_df() -> pd.DataFrame:
    res_by_agents = st.session_state.simulation_results.results_by_agent
    lst = []
    for key, val in res_by_agents.items():
        df = pd.DataFrame.from_dict({k.value: v for (k, v) in val.items()}, orient='index')
        df.rename({0: key}, axis=1, inplace=True)
        lst.append(df)
    dfs = pd.concat(lst, axis=1)
    return dfs


def results_by_agent_as_df_with_highlight(df: pd.DataFrame, agent_chosen_guid: str) -> pd.io.formats.style.Styler:
    formatted_df = df.style.set_properties(subset=[agent_chosen_guid], **{'background-color': 'lemonchiffon'}).\
        format('{:.2f}')
    return formatted_df


def construct_traded_amount_by_agent_chart(agent_chosen_guid: str,
                                           full_df: pd.DataFrame) -> alt.Chart:
    """
    Plot amount of electricity and heating sold and bought.
    @param agent_chosen_guid: Name of chosen agent
    @param full_df: All trades in simulation results
    @return: Altair chart with plot of sold and bought resources
    """

    df = pd.DataFrame()

    domain = []
    range_color = []
    plot_lst: List[dict] = [{'title': 'Amount of electricity bought', 'color_num': 0,
                            'resource': Resource.ELECTRICITY, 'action': Action.BUY},
                            {'title': 'Amount of electricity sold', 'color_num': 1,
                            'resource': Resource.ELECTRICITY, 'action': Action.SELL},
                            {'title': 'Amount of heating bought', 'color_num': 2,
                            'resource': Resource.HEATING, 'action': Action.BUY},
                            {'title': 'Amount of heating sold', 'color_num': 3,
                            'resource': Resource.HEATING, 'action': Action.SELL}]

    full_df = full_df.loc[full_df['source'] == agent_chosen_guid].drop(['by_external'], axis=1)

    for elem in plot_lst:
        mask = (full_df.resource.values == elem['resource']) & (full_df.action.values == elem['action'])
        if not full_df.loc[mask].empty:
            
            df = pd.concat((df, pd.DataFrame({'period': full_df.loc[mask].period,
                                              'value': full_df.loc[mask].quantity_post_loss,
                                              'variable': elem['title']})))

            domain.append(elem['title'])
            range_color.append(app_constants.ALTAIR_BASE_COLORS[elem['color_num']])

    for elem in plot_lst:
        # Adding zeros for missing timestamps
        missing_timestamps = pd.unique(df.loc[~df.period.isin(df[df.variable == elem['title']].period)].period)
        df = pd.concat((df, pd.DataFrame({'period': missing_timestamps,
                                          'value': 0.0,
                                          'variable': elem['title']})))

    return altair_period_chart(df, domain, range_color)


def altair_period_chart(df: pd.DataFrame, domain: List[str], range_color: List[str]) -> alt.Chart:
    """Altair chart for one or more variables over period."""
    selection = alt.selection_single(fields=['variable'], bind='legend')
    return alt.Chart(df).mark_line(). \
        encode(x=alt.X('period:T', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
               y=alt.Y('value', axis=alt.Axis(title='Energy [kWh]')),
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='variable', title='Variable'),
                        alt.Tooltip(field='value', title='Value')]). \
        add_selection(selection).interactive(bind_y=False)


# @st.cache_data(ttl=3600)
def convert_df_to_csv(df: pd.DataFrame, include_index: bool = False):
    return df.to_csv(index=include_index).encode('utf-8')


def download_df_as_csv_button(df: pd.DataFrame, file_name: str, include_index: bool = False):
    csv = convert_df_to_csv(df, include_index=include_index)
    st.download_button(label='Download as csv',
                       data=csv,
                       file_name=file_name + ".csv")


def display_df_and_make_downloadable(df: pd.DataFrame,
                                     file_name: str,
                                     df_styled: Optional[pd.io.formats.style.Styler] = None,
                                     height: Optional[int] = None):
    if df_styled is not None:
        st.dataframe(df_styled, height=height)
    else:
        st.dataframe(df, height=height)

    download_df_as_csv_button(df, file_name, include_index=True)
    

# @st.cache_data()
def load_results(uploaded_results_file):
    st.session_state.simulation_results = pickle.load(uploaded_results_file)


def agent_diff(default: dict, new: dict):
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
    changed_area_info_params = list(set(default['AreaInfo'].items()) - set(new['AreaInfo'].items()))
    changed_mock_data_params = list(set(default['MockDataConstants'].items()) - set(new['MockDataConstants'].items()))
    return changed_area_info_params, changed_mock_data_params


def display_diff_in_config(default: dict, new: dict):

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

    if len(str_to_disp) > 1:
        for s in str_to_disp:
            st.markdown(s)

    return len(new_agents) > 0
