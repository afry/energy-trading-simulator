
import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import altair as alt

import pandas as pd
from pandas.io.formats.style import Styler

from pkg_resources import resource_filename

import streamlit as st

from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.app import app_constants
from tradingplatformpoc.app.app_functions import download_df_as_csv_button
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.generate_data.generate_mock_data import create_inputs_df
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.results.simulation_results import SimulationResults


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
    title = alt.TitleParams("Price over Time", anchor='middle')
    selection = alt.selection_single(fields=['variable'], bind='legend')
    return alt.Chart(data_to_use, title=title).mark_line(). \
        encode(x=alt.X('period', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
               y=alt.Y('value', axis=alt.Axis(title='Price [SEK]')),
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               strokeDash=alt.StrokeDash('variable', scale=alt.Scale(domain=domain, range=range_dash)),
               opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='variable', title='Variable'),
                        alt.Tooltip(field='value', title='Value')]). \
        add_selection(selection).interactive(bind_y=False)


def construct_static_digital_twin_chart(digital_twin: StaticDigitalTwin, agent_chosen_guid: str,
                                        should_add_hp_to_legend: bool = False) -> \
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
    return altair_period_chart(df, domain, range_color, "Energy production/consumption for " + agent_chosen_guid)


def construct_building_with_heat_pump_chart(agent_chosen: Union[BuildingAgent, PVAgent],
                                            heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]]) -> \
        alt.Chart:
    """
    Constructs a multi-line chart with energy production/consumption levels, with any heat pump workload data in the
    background. If there is no heat_pump_data, will just return construct_static_digital_twin_chart(digital_twin).
    """

    heat_pump_data = heat_pump_levels_dict.get(agent_chosen.guid, {})
    if heat_pump_data == {}:
        return construct_static_digital_twin_chart(agent_chosen.digital_twin, agent_chosen.guid, False)

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

    energy_multiline = construct_static_digital_twin_chart(agent_chosen.digital_twin, agent_chosen.guid, True)
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


# maybe we should move this to simulation_runner/trading_simulator
def construct_prices_df(simulation_results: SimulationResults) -> pd.DataFrame:
    """Constructs a pandas DataFrame on the format which fits Altair, which we use for plots."""
    clearing_prices_df = pd.DataFrame.from_dict(simulation_results.clearing_prices_historical, orient='index')
    clearing_prices_df.index.set_names('period', inplace=True)
    clearing_prices_df = clearing_prices_df.reset_index().melt('period')
    clearing_prices_df['Resource'] = clearing_prices_df['variable']
    clearing_prices_df.variable = app_constants.LOCAL_PRICE_STR

    pricing = simulation_results.pricing
    elec_pricing = [p for p in pricing if p.resource == Resource.ELECTRICITY][0]
    if isinstance(elec_pricing, ElectricityPrice):
        nordpool_data = elec_pricing.nordpool_data
        nordpool_data.name = 'value'
        nordpool_data = nordpool_data.to_frame().reset_index()
        nordpool_data['Resource'] = Resource.ELECTRICITY
        nordpool_data.rename({'datetime': 'period'}, axis=1, inplace=True)
        nordpool_data['period'] = pd.to_datetime(nordpool_data['period'])
        retail_df = nordpool_data.copy()
        gross_prices = elec_pricing.get_electricity_gross_retail_price_from_nordpool_price(retail_df['value'])
        retail_df['value'] = elec_pricing.get_electricity_net_external_price(gross_prices)
        retail_df['variable'] = app_constants.RETAIL_PRICE_STR
        wholesale_df = nordpool_data.copy()
        wholesale_df['value'] = elec_pricing.get_electricity_wholesale_price_from_nordpool_price(wholesale_df['value'])
        wholesale_df['variable'] = app_constants.WHOLESALE_PRICE_STR
        return pd.concat([clearing_prices_df, retail_df, wholesale_df])
    else:
        raise TypeError('Prices are not instance of ElectricityPrice!')


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
        loc[full_df[key].values == value]. \
        drop(cols_to_drop, axis=1). \
        set_index([want_index]). \
        apply(lambda x: x.apply(lambda y: y.name) if isinstance(x.iloc[0], Enum) else x)


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
    temperature_df['above_1_degree'] = temperature_df['temperature'].values >= 1.0
    period = st.session_state.simulation_results.all_trades.period
    temp_mask = pd.DataFrame(period).rename(columns={'period': 'datetime'}).merge(temperature_df, on='datetime',
                                                                                  how='left')['above_1_degree']
    return aggregated_import_and_export_results_df_split_on_mask(temp_mask, ['Above', 'Below'])


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


def results_by_agent_as_df_with_highlight(df: pd.DataFrame, agent_chosen_guid: str) -> Styler:
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

    return altair_period_chart(df, domain, range_color, 'Electricity and Heating Amounts Traded for '
                               + agent_chosen_guid)


def altair_period_chart(df: pd.DataFrame, domain: List[str], range_color: List[str],
                        title_str: str) -> alt.Chart:
    """Altair chart for one or more variables over period."""
    selection = alt.selection_single(fields=['variable'], bind='legend')
    alt_title = alt.TitleParams(title_str, anchor='middle')
    return alt.Chart(df, title=alt_title).mark_line(). \
        encode(x=alt.X('period:T', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
               y=alt.Y('value', axis=alt.Axis(title='Energy [kWh]')),
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='variable', title='Variable'),
                        alt.Tooltip(field='value', title='Value')]). \
        add_selection(selection).interactive(bind_y=False)


def display_df_and_make_downloadable(df: pd.DataFrame,
                                     file_name: str,
                                     df_styled: Optional[Styler] = None,
                                     height: Optional[int] = None):
    if df_styled is not None:
        st.dataframe(df_styled, height=height)
    else:
        st.dataframe(df, height=height)

    download_df_as_csv_button(df, file_name, include_index=True)


def color_in(val):
    if 'Running' in val:
        color = '#f7a34f'
    elif 'Completed' in val:
        color = '#5eab7e'
    else:
        color = '#f01d5c'
    return 'color: %s' % color
