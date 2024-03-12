from typing import List

import altair as alt

import pandas as pd

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import Action, Resource


def altair_base_chart(df: pd.DataFrame, domain: List[str], range_color: List[str],
                      var_title_str: str, title_str: str, legend: bool) -> alt.Chart:
    """Altair chart for one or more variables over period, without specified mark."""
    selection = alt.selection_multi(fields=['variable'], bind='legend')
    alt_title = alt.TitleParams(title_str, anchor='middle')
    chart = alt.Chart(df, title=alt_title). \
        encode(x=alt.X('period:T', axis=alt.Axis(title='Period (UTC)'), scale=alt.Scale(type="utc")),
               y=alt.Y('value', axis=alt.Axis(title=var_title_str), stack=None),
               opacity=alt.condition(selection, alt.value(0.8), alt.value(0.0)),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='variable', title='Variable'),
                        alt.Tooltip(field='value', title='Value')]). \
        add_selection(selection).interactive(bind_y=False)
    if legend:
        return chart.encode(color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)))
    else:
        return chart.encode(color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color), legend=None))


def altair_line_chart(df: pd.DataFrame, domain: List[str], range_color: List[str],
                      range_dash: List[List[int]], var_title_str: str, title_str: str,
                      legend: bool = True) -> alt.Chart:
    """Altair base chart with line mark."""
    return altair_base_chart(df, domain, range_color, var_title_str, title_str, legend).encode(
        strokeDash=alt.StrokeDash('variable', scale=alt.Scale(domain=domain, range=range_dash))).mark_line()


def altair_area_chart(df: pd.DataFrame, domain: List[str], range_color: List[str],
                      var_title_str: str, title_str: str, legend: bool = False) -> alt.Chart:
    """Altair base chart with area mark."""
    return altair_base_chart(df, domain, range_color, var_title_str, title_str, legend)\
        .mark_area(interpolate='step-after')


def construct_agent_energy_chart(digital_twin: StaticDigitalTwin, agent_chosen_guid: str,
                                 heat_pump_df: pd.DataFrame) -> alt.Chart:
    """
    Constructs a multi-line chart from a StaticDigitalTwin, containing all data held therein.
    """
    df = pd.DataFrame()
    # Defining colors manually, so that for example heat consumption has the same color for every agent, even if for
    # example electricity production doesn't exist for one of them.
    domain: List[str] = []
    range_color: List[str] = []
    df = add_to_df_and_lists(df, digital_twin.electricity_production, domain, range_color,
                             "Electricity production", app_constants.ALTAIR_BASE_COLORS[0])
    df = add_to_df_and_lists(df, digital_twin.electricity_usage, domain, range_color,
                             "Electricity consumption", app_constants.ALTAIR_BASE_COLORS[1])
    df = add_to_df_and_lists(df, digital_twin.hot_water_production, domain, range_color,
                             "High heat production", app_constants.ALTAIR_BASE_COLORS[2])
    df = add_to_df_and_lists(df, digital_twin.hot_water_usage, domain, range_color,
                             "High heat consumption", app_constants.ALTAIR_BASE_COLORS[3])
    df = add_to_df_and_lists(df, digital_twin.space_heating_production, domain, range_color,
                             "Low heat production", app_constants.ALTAIR_BASE_COLORS[4])
    df = add_to_df_and_lists(df, digital_twin.space_heating_usage, domain, range_color,
                             "Low heat consumption", app_constants.ALTAIR_BASE_COLORS[5])
    df = add_to_df_and_lists(df, digital_twin.cooling_usage, domain, range_color,
                             "Cooling consumption", app_constants.ALTAIR_BASE_COLORS[6])
    df = add_to_df_and_lists(df, digital_twin.cooling_production, domain, range_color,
                             "Cooling production", app_constants.ALTAIR_BASE_COLORS[7])
    if len(heat_pump_df.index) > 0:
        df = add_to_df_and_lists(df, heat_pump_df['level_high'], domain, range_color,
                                 "HP high heat production", app_constants.ALTAIR_BASE_COLORS[8])
        df = add_to_df_and_lists(df, heat_pump_df['level_low'], domain, range_color,
                                 "HP low heat production", app_constants.ALTAIR_BASE_COLORS[9])
    return altair_line_chart(df, domain, range_color, [], "Energy [kWh]",
                             "Energy production/consumption for " + agent_chosen_guid)


def add_to_df_and_lists(df: pd.DataFrame, series: pd.Series, domain: List[str], range_color: List[str], var_name: str,
                        color: str):
    if series is not None:
        df = pd.concat((df, pd.DataFrame({'period': series.index,
                                          'value': series.values,
                                          'variable': var_name})))
        if (df.value != 0).any():
            domain.append(var_name)
            range_color.append(color)
    return df


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
    plot_lst: List[dict] = []
    col_counter = 0
    for resource in [Resource.ELECTRICITY, Resource.HIGH_TEMP_HEAT, Resource.LOW_TEMP_HEAT, Resource.COOLING]:
        plot_lst.append({'title': 'Amount of {} bought'.format(resource.get_display_name()),
                         'color_num': col_counter, 'resource': resource, 'action': Action.BUY})
        plot_lst.append({'title': 'Amount of {} sold'.format(resource.get_display_name()),
                         'color_num': col_counter + 1, 'resource': resource, 'action': Action.SELL})
        col_counter = col_counter + 2

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
                             'Energy traded for ' + agent_chosen_guid)


def construct_price_chart(prices_df: pd.DataFrame, resource: Resource) -> alt.Chart:
    data_to_use = prices_df.loc[prices_df['Resource'] == resource].drop('Resource', axis=1)
    domain = [app_constants.LOCAL_PRICE_STR, app_constants.RETAIL_PRICE_STR, app_constants.WHOLESALE_PRICE_STR]
    range_color = ['blue', 'green', 'red']
    range_dash = [[0, 0], [2, 4], [2, 4]]
    return altair_line_chart(data_to_use, domain, range_color, range_dash, "Price [SEK]", "Price over Time")


def construct_storage_level_chart(storage_levels_df: pd.DataFrame) -> alt.Chart:
    storage_levels_df = storage_levels_df.reset_index()
    storage_levels_df['variable'] = 'Charging level'
    storage_levels_df = storage_levels_df.rename(columns={'level': 'value'})
    domain = list(pd.unique(storage_levels_df['variable']))
    range_color = [app_constants.BATTERY_CHART_COLOR]
    range_dash = [[0, 0]]
    chart = altair_line_chart(storage_levels_df, domain, range_color, range_dash, "% of capacity used",
                              "Charging level")
    chart.encoding.y.axis = alt.Axis(format='%')
    chart.encoding.tooltip[2].format = '.2%'
    return chart

    
def construct_avg_day_elec_chart(elec_use_df: pd.DataFrame, period: tuple) -> alt.Chart:
    """
    Creates a chart of average monthly electricity use with points and error bars.
    The points are colored by the weekday.
    """

    title_str = "Average hourly net electricity consumed from " + period[0] + " to " + period[1]
    var_title_str = "Average of net electricity consumed [kWh]"
    domain = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    range_color = app_constants.ALTAIR_BASE_COLORS[:len(domain)]

    alt_title = alt.TitleParams(title_str, anchor='middle')
    selection = alt.selection_multi(fields=['weekday'], bind='legend')

    elec_use_df['ymin'] = elec_use_df['mean_total_elec'] - elec_use_df['std_total_elec']
    elec_use_df['ymax'] = elec_use_df['mean_total_elec'] + elec_use_df['std_total_elec']

    base = alt.Chart(elec_use_df, title=alt_title)

    points = base.mark_point(filled=True, size=80).encode(
        x=alt.X('hour', axis=alt.Axis(title='Hour')),
        y=alt.Y('mean_total_elec:Q', axis=alt.Axis(title=var_title_str), scale=alt.Scale(zero=False)),
        color=alt.Color('weekday', scale=alt.Scale(domain=domain, range=range_color)),
        opacity=alt.condition(selection, alt.value(0.7), alt.value(0.0))
    )

    error_bars = base.mark_rule(strokeWidth=2).encode(
        x='hour',
        y='ymin:Q',
        y2='ymax:Q',
        color=alt.Color('weekday', scale=alt.Scale(domain=domain, range=range_color)),
        opacity=alt.condition(selection, alt.value(0.8), alt.value(0.0))
    )

    combined_chart = points + error_bars

    return combined_chart.add_selection(selection).interactive(bind_y=False)
