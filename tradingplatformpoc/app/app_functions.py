import altair as alt

import pandas as pd

from pkg_resources import resource_filename

import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from streamlit.type_util import OptionSequence

from tradingplatformpoc import data_store
from tradingplatformpoc.app.app_constants import DATA_PATH, LOCAL_PRICE_STR, RETAIL_PRICE_STR, WHOLESALE_PRICE_STR


def get_price_df_when_local_price_inbetween(prices_df: pd.DataFrame) -> pd.DataFrame:
    """Local price is almost always either equal to the external wholesale or retail price. This method returns the
    subsection of the prices dataframe where the local price is _not_ equal to either of these two."""
    price_df_dt_index = prices_df.set_index("period")
    local_price_between_external = (price_df_dt_index[LOCAL_PRICE_STR]
                                    > price_df_dt_index[WHOLESALE_PRICE_STR]
                                    + 0.0001) & (price_df_dt_index[LOCAL_PRICE_STR]
                                                 < price_df_dt_index[RETAIL_PRICE_STR] - 0.0001)
    return price_df_dt_index.loc[local_price_between_external]


def construct_price_chart(prices_df: pd.DataFrame) -> alt.Chart:
    prices_df = prices_df.melt('period')  # Un-pivot the dataframe from wide to long, which is how Altair prefers it
    domain = [LOCAL_PRICE_STR, RETAIL_PRICE_STR, WHOLESALE_PRICE_STR]
    range_color = ['blue', 'green', 'red']
    range_dash = [[0, 0], [2, 4], [2, 4]]
    return alt.Chart(prices_df).mark_line(). \
        encode(x='period',
               y='value',
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               strokeDash=alt.StrokeDash('variable', scale=alt.Scale(domain=domain, range=range_dash))). \
        interactive(bind_y=False)


@st.cache
def load_data():
    clearing_prices_df = pd.read_csv("clearing_prices.csv")
    clearing_prices_df['period'] = pd.to_datetime(clearing_prices_df['period'])
    clearing_prices_df.rename({'price': LOCAL_PRICE_STR}, axis=1, inplace=True)

    external_price_csv_path = resource_filename(DATA_PATH, "nordpool_area_grid_el_price.csv")
    nordpool_data = data_store.read_nordpool_data(external_price_csv_path)
    nordpool_data.name = 'nordpool'

    prices_df = clearing_prices_df.merge(nordpool_data, left_on="period", right_index=True)
    prices_df[RETAIL_PRICE_STR] = prices_df['nordpool'] + data_store.ELECTRICITY_RETAIL_PRICE_OFFSET
    prices_df[WHOLESALE_PRICE_STR] = prices_df['nordpool'] + data_store.ELECTRICITY_WHOLESALE_PRICE_OFFSET
    prices_df.drop(['nordpool'], axis=1, inplace=True)

    all_bids = pd.read_csv("bids.csv")
    all_bids['period'] = pd.to_datetime(all_bids['period'])
    all_bids.drop(['by_external'], axis=1, inplace=True)  # Don't need this column

    all_trades = pd.read_csv("trades.csv")
    all_trades['period'] = pd.to_datetime(all_trades['period'])
    all_trades.drop(['by_external'], axis=1, inplace=True)  # Don't need this column

    return prices_df, all_bids, all_trades


def select_page_radio(placeholder: DeltaGenerator, label, selections: OptionSequence, disabled: bool) -> str:
    return placeholder.radio(label, selections, disabled=disabled)
