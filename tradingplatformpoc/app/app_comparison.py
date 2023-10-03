from typing import Dict, List

import altair as alt

import pandas as pd

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.app.app_charts import altair_area_chart, altair_line_chart
from tradingplatformpoc.app.app_data_display import get_total_profit_net
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import TradeMetadataKey
from tradingplatformpoc.sql.clearing_price.crud import db_to_construct_local_prices_df
from tradingplatformpoc.sql.level.crud import db_to_viewable_level_df_by_agent
from tradingplatformpoc.sql.trade.crud import get_import_export_df, get_total_grid_fee_paid_on_internal_trades, \
    get_total_tax_paid


def get_net_profit_metrics(job_id: str) -> List[float]:
    sold, bought = get_total_profit_net(job_id)
    tax = get_total_tax_paid(job_id)
    grid_fee = get_total_grid_fee_paid_on_internal_trades(job_id=job_id)
    net_profit = sold - bought - tax - grid_fee
    return [net_profit, sold, bought, tax, grid_fee]


def construct_comparison_price_chart(ids: List[Dict[str, str]]) -> alt.Chart:
    local_price_dfs = []
    for comp_id in ids:
        local_price_df = db_to_construct_local_prices_df(comp_id["job_id"])
        local_price_df['variable'] = app_constants.LOCAL_PRICE_STR + ' - ' + comp_id["config_id"]
        local_price_dfs.append(local_price_df)
    
    combined_price_df = pd.concat(local_price_dfs)
    combined_price_df_domain = list(pd.unique(combined_price_df['variable']))

    data_to_use = combined_price_df.loc[
        combined_price_df['Resource'] == Resource.ELECTRICITY].drop('Resource', axis=1)

    return altair_line_chart(data_to_use, combined_price_df_domain,
                             app_constants.ALTAIR_BASE_COLORS[:len(combined_price_df_domain)],
                             app_constants.ALTAIR_STROKE_DASH[:len(combined_price_df_domain)],
                             "Price [SEK]", "Price over Time")


def import_export_altair_period_chart(ids: List[Dict[str, str]]) -> alt.Chart:

    # Get data from database
    df = get_import_export_df([elem["job_id"] for elem in ids])

    # What's sold by the external grid agents is imported by the local grid and vice versa
    var_names = {
        (Action.SELL, Resource.HEATING): "Heat, imported",
        (Action.BUY, Resource.HEATING): "Heat, exported",
        (Action.SELL, Resource.ELECTRICITY): "Electricity, imported",
        (Action.BUY, Resource.ELECTRICITY): "Electricity, exported"}
    
    colors: List[str] = [""] * (len(app_constants.ALTAIR_BASE_COLORS[:4]) + len(app_constants.ALTAIR_DARK_COLORS[:4]))
    colors[::2] = app_constants.ALTAIR_BASE_COLORS[:4]
    colors[1::2] = app_constants.ALTAIR_DARK_COLORS[:4]

    # Process data to be of a form that fits the altair chart
    domain: List[str] = []
    range_color: List[str] = []
    range_dash: List[List[int]] = []
    j = 0
    new_df = pd.DataFrame()
    for action in [Action.BUY, Action.SELL]:
        for resource in [Resource.HEATING, Resource.ELECTRICITY]:
            for job_id in pd.unique(df.job_id):
                subset = df[(df.action == action) & (df.resource == resource) & (df.job_id == job_id)][
                    ['period', 'quantity_post_loss']]
                
                if not subset.empty:
                    subset = subset.set_index('period')
                    datetime_range = pd.date_range(start=subset.index.min(), end=subset.index.max(),
                                                   freq="1h", tz='utc')
                    subset = subset.reindex(datetime_range).fillna(0)
                    subset = subset.reset_index().rename(columns={'index': 'period'})
                    variable = var_names[(action, resource)] + ' - ' + \
                        [elem['config_id'] for elem in ids if elem["job_id"] == job_id][0]
                    subset['variable'] = variable
                    subset = subset.rename(columns={'quantity_post_loss': 'value'})

                    domain.append(variable)
                    range_color.append(colors[j])
                    range_dash.append(app_constants.ALTAIR_STROKE_DASH[j % 2])

                    new_df = pd.concat((new_df, subset))
                j = j + 1
    return altair_line_chart(new_df, domain, range_color, range_dash, "Energy [kWh]",
                             'Import and export of resources through trades with grid agents')


def construct_level_comparison_chart(ids: List[Dict[str, str]], agent_names: List[str],
                                     level_type: TradeMetadataKey, var_title_str: str, title_str: str,
                                     num_letters: int = 7) -> alt.Chart:
    level_dfs = []
    for comp_id, agent_name in zip(ids, agent_names):
        agent_var = agent_name[:num_letters] + '...' + agent_name[-num_letters:] \
            if (len(agent_name) > 2 * num_letters) else agent_name
        level_dfs.append(db_to_viewable_level_df_by_agent(
            job_id=comp_id['job_id'],
            agent_guid=agent_name,
            level_type=level_type.name)
            .assign(variable=agent_var + ' - ' + comp_id['config_id']))

        combined_level_df = pd.concat(level_dfs, axis=0, join="outer").reset_index()

    combined_level_df = combined_level_df.rename(columns={'level': 'value'})
    domain = list(pd.unique(combined_level_df['variable']))
    range_color = app_constants.ALTAIR_BASE_COLORS[:len(domain)]

    return altair_area_chart(combined_level_df, domain, range_color, var_title_str, title_str, True)
