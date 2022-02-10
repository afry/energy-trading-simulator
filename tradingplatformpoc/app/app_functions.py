import altair as alt

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

import streamlit as st

from tradingplatformpoc import data_store
from tradingplatformpoc.app.app_constants import DATA_PATH, LOCAL_PRICE_STR, RETAIL_PRICE_STR, WHOLESALE_PRICE_STR
from tradingplatformpoc.bid import Resource


def get_price_df_when_local_price_inbetween(prices_df: pd.DataFrame) -> pd.DataFrame:
    """Local price is almost always either equal to the external wholesale or retail price. This method returns the
    subsection of the prices dataframe where the local price is _not_ equal to either of these two."""
    price_df_dt_index = prices_df.set_index("period")
    local_price_between_external = (price_df_dt_index[LOCAL_PRICE_STR]
                                    > price_df_dt_index[WHOLESALE_PRICE_STR]
                                    + 0.0001) & (price_df_dt_index[LOCAL_PRICE_STR]
                                                 < price_df_dt_index[RETAIL_PRICE_STR] - 0.0001)
    return price_df_dt_index.loc[local_price_between_external]


def construct_price_chart(prices_df: pd.DataFrame, resource: Resource) -> alt.Chart:
    data_to_use = prices_df.loc[prices_df['Resource'] == resource].drop('Resource', axis=1)
    domain = [LOCAL_PRICE_STR, RETAIL_PRICE_STR, WHOLESALE_PRICE_STR]
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


def construct_storage_level_chart(storage_levels_df: pd.DataFrame, agent: str) -> alt.Chart:
    storage_levels = storage_levels_df.loc[storage_levels_df.agent == agent]
    return alt.Chart(storage_levels).mark_line(). \
        encode(x=alt.X('period', axis=alt.Axis(title='Period')),
               y=alt.Y('capacity_kwh', axis=alt.Axis(title='Capacity [kWh]')),
               tooltip=[alt.Tooltip(field='period', title='Period', type='temporal', format='%Y-%m-%d %H:%M'),
                        alt.Tooltip(field='capacity_kwh', title='Capacity [kWh]')]). \
        interactive(bind_y=False)


@st.cache
def load_data(results_path: str):
    clearing_prices_df = pd.read_csv(results_path + "clearing_prices.csv")
    clearing_prices_df['period'] = pd.to_datetime(clearing_prices_df['period'])
    # Un-pivot the dataframe from wide to long, which is how Altair prefers it
    clearing_prices_df = clearing_prices_df.melt('period')
    clearing_prices_df['Resource'] = np.where(clearing_prices_df.variable == 'electricity', Resource.ELECTRICITY,
                                              Resource.HEATING)
    clearing_prices_df.variable = LOCAL_PRICE_STR

    external_price_csv_path = resource_filename(DATA_PATH, "nordpool_area_grid_el_price.csv")
    nordpool_data = data_store.read_nordpool_data(external_price_csv_path)
    nordpool_data.name = 'value'
    nordpool_data = nordpool_data.to_frame().reset_index()
    nordpool_data['Resource'] = Resource.ELECTRICITY
    nordpool_data.rename({'datetime': 'period'}, axis=1, inplace=True)
    nordpool_data['period'] = pd.to_datetime(nordpool_data['period'])
    retail_df = nordpool_data.copy()
    retail_df['value'] = retail_df['value'] + data_store.ELECTRICITY_RETAIL_PRICE_OFFSET
    retail_df['variable'] = RETAIL_PRICE_STR
    wholesale_df = nordpool_data.copy()
    wholesale_df['value'] = wholesale_df['value'] + data_store.ELECTRICITY_WHOLESALE_PRICE_OFFSET
    wholesale_df['variable'] = WHOLESALE_PRICE_STR

    prices_df = pd.concat([clearing_prices_df, retail_df, wholesale_df])

    all_bids = pd.read_csv(results_path + "bids.csv")
    all_bids['period'] = pd.to_datetime(all_bids['period'])
    all_bids.drop(['by_external'], axis=1, inplace=True)  # Don't need this column

    all_trades = pd.read_csv(results_path + "trades.csv")
    all_trades['period'] = pd.to_datetime(all_trades['period'])
    all_trades.drop(['by_external'], axis=1, inplace=True)  # Don't need this column

    storage_levels = pd.read_csv(results_path + "storages.csv")
    storage_levels['period'] = pd.to_datetime(storage_levels['period'])

    return prices_df, all_bids, all_trades, storage_levels
