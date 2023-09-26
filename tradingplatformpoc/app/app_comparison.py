from typing import Dict, List

import pandas as pd

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.app.app_visualizations import altair_period_chart
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.sql.trade.crud import get_import_export_df


def import_export_altair_period_chart(ids: List[Dict[str, str]]):

    # Get data from database
    df = get_import_export_df([elem["job_id"] for elem in ids])

    var_names = {
        (Action.BUY, Resource.HEATING): "Heat, imported",
        (Action.SELL, Resource.HEATING): "Heat, exported",
        (Action.BUY, Resource.ELECTRICITY): "Electricity, imported",
        (Action.SELL, Resource.ELECTRICITY): "Electricity, exported"}

    # Process data to be of a form that fits the altair chart
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
            
                subset['variable'] = var_names[(action, resource)] + ' - ' + \
                    [elem['config_id'] for elem in ids if elem["job_id"] == job_id][0]
                subset = subset.rename(columns={'quantity_post_loss': 'value'})
                new_df = pd.concat((new_df, subset))
    domain = list(pd.unique(new_df['variable']))
    return altair_period_chart(new_df, domain, app_constants.ALTAIR_BASE_COLORS[:len(domain)],
                               'Import and export of resources through trades with grid agents')
