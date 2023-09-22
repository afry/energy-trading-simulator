import pandas as pd

from tradingplatformpoc.market.bid import Action, Resource


def convert_to_altair_df(df: pd.DataFrame):

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
            
                subset['variable'] = action.name + resource.name + job_id
                subset = subset.rename(columns={'quantity_post_loss': 'value'})
                new_df = pd.concat((new_df, subset))
    return new_df, list(pd.unique(new_df['variable']))
