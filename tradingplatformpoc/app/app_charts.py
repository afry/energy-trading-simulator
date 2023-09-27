from typing import List

import altair as alt

import pandas as pd

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import Action, Resource


def altair_base_chart(df: pd.DataFrame, domain: List[str], range_color: List[str],
                      var_title_str: str, title_str: str) -> alt.Chart:
    """Altair chart for one or more variables over period, without specified mark."""
    selection = alt.selection_multi(fields=['variable'], bind='legend')
    alt_title = alt.TitleParams(title_str, anchor='middle')
    return alt.Chart(df, title=alt_title). \
        encode(x=alt.X('period:T', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
               y=alt.Y('value', axis=alt.Axis(title=var_title_str)),
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               opacity=alt.condition(selection, alt.value(1), alt.value(0.2)),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='variable', title='Variable'),
                        alt.Tooltip(field='value', title='Value')]). \
        add_selection(selection).interactive(bind_y=False)


def altair_line_chart(df: pd.DataFrame, domain: List[str], range_color: List[str],
                      range_dash: List[List[int]], var_title_str: str, title_str: str) -> alt.Chart:
    """Altair base chart with line mark."""
    return altair_base_chart(df, domain, range_color, var_title_str, title_str).encode(
        strokeDash=alt.StrokeDash('variable', scale=alt.Scale(domain=domain, range=range_dash))).mark_line()


def altair_area_chart(df: pd.DataFrame, domain: List[str], range_color: List[str],
                      var_title_str: str, title_str: str) -> alt.Chart:
    """Altair base chart with area mark."""
    return altair_base_chart(df, domain, range_color, var_title_str, title_str).mark_area(interpolate='step-after')


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
        if (df.value != 0).any():
            domain.append(app_constants.ELEC_PROD)
            range_color.append(app_constants.ALTAIR_BASE_COLORS[0])
    if digital_twin.electricity_usage is not None:
        df = pd.concat((df, pd.DataFrame({'period': digital_twin.electricity_usage.index,
                                          'value': digital_twin.electricity_usage.values,
                                          'variable': app_constants.ELEC_CONS})))
        if (df.value != 0).any():
            domain.append(app_constants.ELEC_CONS)
            range_color.append(app_constants.ALTAIR_BASE_COLORS[1])
    if digital_twin.heating_production is not None:
        df = pd.concat((df, pd.DataFrame({'period': digital_twin.heating_production.index,
                                          'value': digital_twin.heating_production.values,
                                          'variable': app_constants.HEAT_PROD})))
        if (df.value != 0).any():
            domain.append(app_constants.HEAT_PROD)
            range_color.append(app_constants.ALTAIR_BASE_COLORS[2])
    if digital_twin.heating_usage is not None:
        df = pd.concat((df, pd.DataFrame({'period': digital_twin.heating_usage.index,
                                          'value': digital_twin.heating_usage.values,
                                          'variable': app_constants.HEAT_CONS})))
        if (df.value != 0).any():
            domain.append(app_constants.HEAT_CONS)
            range_color.append(app_constants.ALTAIR_BASE_COLORS[3])
    if should_add_hp_to_legend:
        domain.append('Heat pump workload')
        range_color.append(app_constants.HEAT_PUMP_CHART_COLOR)
    return altair_line_chart(df, domain, range_color, [], "Energy [kWh]",
                             "Energy production/consumption for " + agent_chosen_guid)


def construct_traded_amount_by_agent_chart(agent_chosen_guid: str,
                                           agent_trade_df: pd.DataFrame) -> alt.Chart:
    """
    Plot amount of electricity and heating sold and bought.
    @param agent_chosen_guid: Name of chosen agent
    @param agent_trade_df: All trades by agent
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

    for elem in plot_lst:
        mask = (agent_trade_df.resource.values == elem['resource'].name) \
            & (agent_trade_df.action.values == elem['action'].name)
        if not agent_trade_df.loc[mask].empty:
            
            df = pd.concat((df, pd.DataFrame({'period': agent_trade_df.loc[mask].index,
                                              'value': agent_trade_df.loc[mask].quantity_post_loss,
                                              'variable': elem['title']})))

            domain.append(elem['title'])
            range_color.append(app_constants.ALTAIR_BASE_COLORS[elem['color_num']])

    for elem in plot_lst:
        # Adding zeros for missing timestamps
        missing_timestamps = pd.unique(df.loc[~df.period.isin(df[df.variable == elem['title']].period)].period)
        df = pd.concat((df, pd.DataFrame({'period': missing_timestamps,
                                          'value': 0.0,
                                          'variable': elem['title']})))

    return altair_line_chart(df, domain, range_color, [], "Energy [kWh]",
                             'Electricity and Heating Amounts Traded for ' + agent_chosen_guid)


def construct_price_chart(prices_df: pd.DataFrame, resource: Resource) -> alt.Chart:
    data_to_use = prices_df.loc[prices_df['Resource'] == resource].drop('Resource', axis=1)
    domain = [app_constants.LOCAL_PRICE_STR, app_constants.RETAIL_PRICE_STR, app_constants.WHOLESALE_PRICE_STR]
    range_color = ['blue', 'green', 'red']
    range_dash = [[0, 0], [2, 4], [2, 4]]
    return altair_line_chart(data_to_use, domain, range_color, range_dash, "Price [SEK]", "Price over Time")


def construct_building_with_heat_pump_chart(agent_chosen_guid: str, digital_twin: StaticDigitalTwin,
                                            heat_pump_df: pd.DataFrame) -> \
        alt.Chart:
    """
    Constructs a multi-line chart with energy production/consumption levels, with any heat pump workload data in the
    background. If there is no heat_pump_data, will just return construct_static_digital_twin_chart(digital_twin).
    """

    if heat_pump_df.empty:
        return construct_static_digital_twin_chart(digital_twin, agent_chosen_guid, False)

    heat_pump_df.columns = ['period', 'Heat pump workload']
    heat_pump_area = alt.Chart(heat_pump_df). \
        mark_area(color=app_constants.HEAT_PUMP_CHART_COLOR, opacity=0.3, interpolate='step-after'). \
        encode(
        x=alt.X('period:T', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
        y=alt.Y('Heat pump workload', axis=alt.Axis(title='Heat pump workload', titleColor='gray')),
        tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                 alt.Tooltip(field='Heat pump workload', title='Heat pump workload', type='quantitative')]
    )

    energy_multiline = construct_static_digital_twin_chart(digital_twin, agent_chosen_guid, True)
    return alt.layer(heat_pump_area, energy_multiline).resolve_scale(y='independent')


def construct_storage_level_chart(storage_levels: pd.DataFrame) -> alt.Chart:
    return alt.Chart(storage_levels.reset_index()).mark_line(). \
        encode(x=alt.X('period', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
               y=alt.Y('level', axis=alt.Axis(title='Capacity [kWh]')),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='level', title='Capacity [kWh]')]). \
        interactive(bind_y=False)
