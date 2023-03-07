import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Union

import altair as alt

import pandas as pd

from pkg_resources import resource_filename

from scripts.extract_df_from_mock_datas_pickle_file import DATA_PATH

import streamlit as st

from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.app import app_constants
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.generate_mock_data import create_inputs_df
from tradingplatformpoc.heat_pump import DEFAULT_COP
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
        encode(x=alt.X('period', axis=alt.Axis(title='Period')),
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
        x=alt.X('period:T', axis=alt.Axis(title='Period')),
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
        encode(x=alt.X('period', axis=alt.Axis(title='Period')),
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


def remove_agent(some_agent: Dict[str, Any]):
    st.session_state.config_data['Agents'].remove(some_agent)


def duplicate_agent(some_agent: Dict[str, Any]):
    """
    Takes a copy of the input agent, modifies the name (making sure that no other agent has exactly that name), and adds
    it to the session_state list of agents.
    """
    new_agent = some_agent.copy()
    all_agent_names = [agent['Name'] for agent in st.session_state.config_data['Agents']]
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
    Adds the argument agent to the session_state list of agents. Keeps track of how many agents have been added since
    session startup (again using session_state) and names the new agent accordingly: The first will be named
    'NewAgent1', the second 'NewAgent2' etc.
    """
    if 'agents_added' not in st.session_state:
        st.session_state.agents_added = 1
    else:
        st.session_state.agents_added += 1
    new_agent["Name"] = "NewAgent" + str(st.session_state.agents_added)
    st.session_state.config_data['Agents'].append(new_agent)


def add_building_agent():
    add_agent({
        "Type": "BuildingAgent",
        "GrossFloorArea": 1000.0
    })


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


def add_pv_agent():
    add_agent({
        "Type": "PVAgent",
        "PVArea": 100
    })


def add_grocery_store_agent():
    add_agent({
        "Type": "GroceryStoreAgent",
        "PVArea": 320
    })


def add_grid_agent():
    add_agent({
        "Type": "GridAgent",
        "Resource": "ELECTRICITY",
        "TransferRate": 10000
    })


def agent_inputs(agent):
    """Contains input fields needed to define an agent."""
    form = st.form(key="Form" + agent['Name'])
    agent['Name'] = form.text_input('Name', key='NameField' + agent['Name'], value=agent['Name'])
    agent['Type'] = form.selectbox('Type', options=ALL_AGENT_TYPES,
                                   key='TypeSelectBox' + agent['Name'],
                                   index=ALL_AGENT_TYPES.index(agent['Type']))
    if agent['Type'] == 'BuildingAgent':
        agent['GrossFloorArea'] = form.number_input(
            'Gross floor area (sqm)', min_value=0.0, step=10.0,
            value=float(agent['GrossFloorArea']),
            help=app_constants.GROSS_FLOOR_AREA_HELP_TEXT,
            key='GrossFloorArea' + agent['Name']
        )
        agent['FractionCommercial'] = form.number_input(
            'Fraction commercial', min_value=0.0, max_value=1.0,
            value=get_if_exists_else(agent, 'FractionCommercial', 0.0),
            help=app_constants.FRACTION_COMMERCIAL_HELP_TEXT,
            key='FractionCommercial' + agent['Name']
        )
        agent['FractionSchool'] = form.number_input(
            'Fraction school', min_value=0.0, max_value=1.0,
            value=get_if_exists_else(agent, 'FractionSchool', 0.0),
            help=app_constants.FRACTION_SCHOOL_HELP_TEXT,
            key='FractionSchool' + agent['Name']
        )
    if agent['Type'] in ['StorageAgent', 'GridAgent']:
        agent['Resource'] = form.selectbox('Resource', options=ALL_IMPLEMENTED_RESOURCES_STR,
                                           key='ResourceSelectBox' + agent['Name'],
                                           index=ALL_IMPLEMENTED_RESOURCES_STR.index(agent['Resource']))
    if agent['Type'] == 'StorageAgent':
        agent['Capacity'] = form.number_input(
            'Capacity', min_value=0.0, step=1.0,
            value=float(agent['Capacity']),
            help=app_constants.CAPACITY_HELP_TEXT,
            key='Capacity' + agent['Name']
        )
        agent['ChargeRate'] = form.number_input(
            'Charge rate', min_value=0.01, max_value=10.0,
            value=float(agent['ChargeRate']),
            help=app_constants.CHARGE_RATE_HELP_TEXT,
            key='ChargeRate' + agent['Name']
        )
        agent['RoundTripEfficiency'] = form.number_input(
            'Round-trip efficiency', min_value=0.01, max_value=1.0,
            value=float(agent['RoundTripEfficiency']),
            help=app_constants.ROUND_TRIP_EFFICIENCY_HELP_TEXT,
            key='RoundTripEfficiency' + agent['Name']
        )
        agent['NHoursBack'] = int(form.number_input(
            '\'N hours back\'', min_value=1, max_value=8760,
            value=int(agent['NHoursBack']),
            help=app_constants.N_HOURS_BACK_HELP_TEXT,
            key='NHoursBack' + agent['Name']
        ))
        agent['BuyPricePercentile'] = form.number_input(
            '\'Buy-price percentile\'', min_value=0.0, max_value=100.0, step=1.0,
            value=float(agent['BuyPricePercentile']),
            help=app_constants.BUY_PERC_HELP_TEXT,
            key='BuyPricePercentile' + agent['Name']
        )
        agent['SellPricePercentile'] = form.number_input(
            '\'Sell-price percentile\'', min_value=0.0, max_value=100.0, step=1.0,
            value=float(agent['SellPricePercentile']),
            help=app_constants.SELL_PERC_HELP_TEXT,
            key='SellPricePercentile' + agent['Name']
        )
        agent['DischargeRate'] = form.number_input(
            'Discharge rate', min_value=0.01, max_value=10.0,
            value=float(get_if_exists_else(agent, 'DischargeRate', agent['ChargeRate'])),
            help=app_constants.DISCHARGE_RATE_HELP_TEXT,
            key='DischargeRate' + agent['Name']
        )
    if agent['Type'] in ['BuildingAgent', 'PVAgent', 'GroceryStoreAgent']:
        agent['PVArea'] = form.number_input(
            'PV area (sqm)', min_value=0.0, format='%.1f', step=10.0,
            value=float(get_if_exists_else(agent, 'PVArea', 0.0)),
            help=app_constants.PV_AREA_HELP_TEXT,
            key='PVArea' + agent['Name']
        )
        agent['PVEfficiency'] = form.number_input(
            'PV efficiency', min_value=0.01, max_value=0.99, format='%.3f',
            value=get_if_exists_else(agent, 'PVEfficiency',
                                     st.session_state.config_data['AreaInfo']['DefaultPVEfficiency']),
            help=app_constants.PV_EFFICIENCY_HELP_TEXT,
            key='PVEfficiency' + agent['Name']
        )
    if agent['Type'] == 'BuildingAgent':
        agent['NumberHeatPumps'] = form.number_input(
            'Heat pumps', min_value=0, step=1,
            value=int(get_if_exists_else(agent, 'NumberHeatPumps', 0)),
            help=app_constants.HEAT_PUMPS_HELP_TEXT,
            key='NumberHeatPumps' + agent['Name']
        )
        agent['COP'] = form.number_input(
            'COP', min_value=2.0, step=0.1,
            value=float(get_if_exists_else(agent, 'COP', DEFAULT_COP)),
            help=app_constants.HEAT_PUMP_COP_HELP_TEXT,
            key='COP' + agent['Name'],
            disabled=(agent['NumberHeatPumps'] == 0)
        )
    if agent['Type'] == 'GridAgent':
        agent['TransferRate'] = form.number_input(
            'Transfer rate', min_value=0.0, step=10.0,
            value=float(agent['TransferRate']),
            help=app_constants.TRANSFER_RATE_HELP_TEXT,
            key='TransferRate' + agent['Name']
        )
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.button('Remove agent', key='RemoveButton' + agent['Name'], on_click=remove_agent, args=(agent,))
        with col2:
            st.button('Duplicate agent', key='DuplicateButton' + agent['Name'], on_click=duplicate_agent, args=(agent,))
    form.form_submit_button('Save agent')


def get_agent(all_agents: Iterable[IAgent], agent_chosen_guid: str) -> IAgent:
    return [x for x in all_agents if x.guid == agent_chosen_guid][0]


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
    df_inputs, df_irrd = create_inputs_df(resource_filename(DATA_PATH, 'temperature_vetelangden.csv'),
                                          resource_filename(DATA_PATH, 'varberg_irradiation_W_m2_h.csv'),
                                          resource_filename(DATA_PATH, 'vetelangden_slim.csv'))
    
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


def results_by_agent_as_df_with_highlight(agent_chosen_guid: str) -> pd.io.formats.style.Styler:
    res_by_agents = st.session_state.simulation_results.results_by_agent
    lst = []
    for key, val in res_by_agents.items():
        df = pd.DataFrame.from_dict({k.value: v for (k, v) in val.items()}, orient='index')
        df.rename({0: key}, axis=1, inplace=True)
        lst.append(df)
    dfs = pd.concat(lst, axis=1)
    formatted_df = dfs.style.set_properties(subset=[agent_chosen_guid], **{'background-color': 'lemonchiffon'}).\
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
    return alt.Chart(df).mark_line(). \
        encode(x=alt.X('period:T', axis=alt.Axis(title='Period')),
               y=alt.Y('value', axis=alt.Axis(title='Energy [kWh]')),
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='variable', title='Variable'),
                        alt.Tooltip(field='value', title='Value')]). \
        interactive(bind_y=False)
