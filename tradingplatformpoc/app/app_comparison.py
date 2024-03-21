from typing import Any, Dict, List, Optional

import altair as alt

import pandas as pd

import streamlit as st

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.app.app_charts import altair_line_chart
from tradingplatformpoc.app.app_functions import IdPair
from tradingplatformpoc.market.trade import Action, Resource, TradeMetadataKey
from tradingplatformpoc.sql.level.crud import db_to_viewable_level_df, db_to_viewable_level_df_by_agent
from tradingplatformpoc.sql.results.models import ResultsKey
from tradingplatformpoc.sql.trade.crud import get_external_trades_df


"""
This file holds functions used in scenario_comparison.py
"""


class ComparisonIds:
    id_pairs: List[IdPair]

    def __init__(self, job_id_per_config_id: Dict[str, str], chosen_config_ids: List[str]):
        self.id_pairs = [IdPair(cid, job_id_per_config_id[cid]) for cid in chosen_config_ids]

    def get_config_ids(self):
        return [elem.config_id for elem in self.id_pairs]

    def get_job_ids(self):
        return [elem.job_id for elem in self.id_pairs]

    def get_job_id(self, config_id: str):
        return [elem.job_id for elem in self.id_pairs if elem.config_id == config_id][0]

    def get_config_id(self, job_id: str):
        return [elem.config_id for elem in self.id_pairs if elem.job_id == job_id][0]


def import_export_calculations(ids: ComparisonIds) -> alt.Chart:

    # Get data from database
    df = get_external_trades_df(ids.get_job_ids())

    # What's sold by the external grid agents is imported by the local grid and vice versa
    var_names = {
        (Action.SELL, Resource.HIGH_TEMP_HEAT): "High-temp heat, imported",
        (Action.SELL, Resource.ELECTRICITY): "Electricity, imported",
        (Action.BUY, Resource.ELECTRICITY): "Electricity, exported"}

    colors: List[str] = app_constants.ALTAIR_BASE_COLORS[:(len(var_names) * 2)]

    # Process data to be of a form that fits the altair chart
    domain: List[str] = []
    range_color: List[str] = []
    range_dash: List[List[int]] = []
    j = 0
    new_df = pd.DataFrame()
    for (k, title) in var_names.items():
        action = k[0]
        resource = k[1]
        for job_id in pd.unique(df.job_id):
            subset = df[(df.resource == resource) & (df.job_id == job_id) & (df.action == action)][[
                'period', 'quantity_post_loss']]

            if not subset.empty:
                subset = subset.set_index('period')
                datetime_range = pd.date_range(start=subset.index.min(), end=subset.index.max(),
                                               freq="1h", tz='utc')
                subset = subset.reindex(datetime_range).fillna(0)
                subset = subset.reset_index().rename(columns={'index': 'period'})
                variable = title + ' - ' + ids.get_config_id(job_id)
                subset['variable'] = variable
                subset = subset.rename(columns={'quantity_post_loss': 'value'})

                domain.append(variable)
                range_color.append(colors[j])
                range_dash.append(app_constants.ALTAIR_STROKE_DASH[j % 2])

                new_df = pd.concat((new_df, subset))
            j = j + 1
    chart = altair_line_chart(new_df, domain, range_color, range_dash, "Energy [kWh]",
                              'Import and export of resources through trades with grid agents')
    return chart


def construct_heat_dump_comparison_chart(ids: ComparisonIds) -> alt.Chart:
    """Process data to be of a form that fits the altair chart, then construct a line chart."""
    domain: List[str] = []
    range_color: List[str] = app_constants.ALTAIR_BASE_COLORS[:2]
    range_dash: List[List[int]] = [[0, 0], [8, 8]]
    new_df = pd.DataFrame()
    for job_id in ids.get_job_ids():
        df = db_to_viewable_level_df(job_id, TradeMetadataKey.HEAT_DUMP.name)
        df = df.reset_index().rename(columns={'index': 'period', 'level': 'value'})
        config_id = ids.get_config_id(job_id)
        df['variable'] = config_id
        new_df = pd.concat((new_df, df))
        domain.append(config_id)

    return altair_line_chart(new_df, domain, range_color, range_dash, "Heat [kWh]", 'Heat dump')


def show_key_figures(pre_calculated_results_1: Dict[str, Any], pre_calculated_results_2: Dict[str, Any]):
    c1, c2 = st.columns(2)
    with c1:
        numbers_first = show_key_figs_for_one(pre_calculated_results_1)
    with c2:
        show_key_figs_for_one(pre_calculated_results_2, numbers_first)


def show_key_figs_for_one(pre_calculated_results: Dict[str, Any], other_numbers: Optional[List[float]] = None) \
        -> List[float]:
    """
    Uses 'other_numbers' to display "delta", a percentage change. Inserts blank lines if other_numbers aren't specified,
    to improve vertical alignment.
    """
    net_import_dict = pre_calculated_results[ResultsKey.SUM_NET_IMPORT]
    numbers = [pre_calculated_results[ResultsKey.NET_ENERGY_SPEND],
               net_import_dict[Resource.ELECTRICITY.name] / 1000,
               net_import_dict[Resource.HIGH_TEMP_HEAT.name] / 1000]
    deltas: List[Optional[str]] = [str(round(100 * (this - other) / other, 2)) + '%'
                                   for this, other in zip(numbers, other_numbers)]\
        if other_numbers else [None] * len(numbers)
    st.metric(label="Total net energy spend:",
              value="{:,.2f} SEK".format(numbers[0]),
              help="The net energy spend is calculated by subtracting the total revenue from energy exports from the "
                   "total expenditure on importing energy.",
              delta=deltas[0],
              delta_color='inverse')
    if deltas[0] is None:
        st.write('\n')
    st.metric(label="Net import of electricity:",
              value="{:,.2f} MWh".format(numbers[1]),
              delta=deltas[1],
              delta_color='inverse')
    if deltas[1] is None:
        st.write('\n')
    st.metric(label="Net import of high-temp heating:",
              value="{:,.2f} MWh".format(numbers[2]),
              delta=deltas[2],
              delta_color='inverse')
    return numbers


def construct_level_comparison_chart(ids: ComparisonIds, agent_names: List[str],
                                     level_type: TradeMetadataKey, var_title_str: str, title_str: str,
                                     num_letters: int = 7) -> Optional[alt.Chart]:
    level_dfs = []
    for comp_id, agent_name in zip(ids.id_pairs, agent_names):
        agent_var = agent_name[:num_letters] + '...' + agent_name[-num_letters:] \
            if (len(agent_name) > 2 * num_letters) else agent_name
        level_dfs.append(db_to_viewable_level_df_by_agent(
            job_id=comp_id.job_id,
            agent_guid=agent_name,
            level_type=level_type.name)
            .assign(variable=agent_var + ' - ' + comp_id.config_id))

    combined_level_df = pd.concat(level_dfs, axis=0, join="outer").reset_index()
    if combined_level_df.empty:
        return None
    combined_level_df = combined_level_df.rename(columns={'level': 'value'})
    domain = list(pd.unique(combined_level_df['variable']))
    range_color = app_constants.ALTAIR_BASE_COLORS[:len(domain)]

    return altair_line_chart(combined_level_df, domain, range_color, [], var_title_str, title_str, True)
