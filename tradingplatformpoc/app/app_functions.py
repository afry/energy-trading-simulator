import json
from typing import Any, Dict

import altair as alt

import numpy as np

import pandas as pd

import streamlit as st

from tradingplatformpoc.app.app_constants import LOCAL_PRICE_STR, RETAIL_PRICE_STR, WHOLESALE_PRICE_STR
from tradingplatformpoc.bid import Resource
from tradingplatformpoc.data_store import DataStore


def get_price_df_when_local_price_inbetween(prices_df: pd.DataFrame, resource: Resource) -> pd.DataFrame:
    """Local price is almost always either equal to the external wholesale or retail price. This method returns the
    subsection of the prices dataframe where the local price is _not_ equal to either of these two."""
    elec_prices = prices_df.\
        loc[prices_df['Resource'] == resource].\
        drop('Resource', axis=1).\
        pivot(index="period", columns="variable")['value']
    local_price_between_external = (elec_prices[LOCAL_PRICE_STR]
                                    > elec_prices[WHOLESALE_PRICE_STR]
                                    + 0.0001) & (elec_prices[LOCAL_PRICE_STR]
                                                 < elec_prices[RETAIL_PRICE_STR] - 0.0001)
    return elec_prices.loc[local_price_between_external]


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

    # Initialize a DataStore
    config_filename = results_path + "config_used.json"
    with open(config_filename, "r") as json_file:
        config_data = json.load(json_file)

    data_store_entity = DataStore.from_csv_files(config_area_info=config_data['AreaInfo'])
    nordpool_data = data_store_entity.nordpool_data
    nordpool_data.name = 'value'
    nordpool_data = nordpool_data.to_frame().reset_index()
    nordpool_data['Resource'] = Resource.ELECTRICITY
    nordpool_data.rename({'datetime': 'period'}, axis=1, inplace=True)
    nordpool_data['period'] = pd.to_datetime(nordpool_data['period'])
    retail_df = nordpool_data.copy()
    retail_df['value'] = retail_df['value'] + data_store_entity.elec_retail_offset
    retail_df['variable'] = RETAIL_PRICE_STR
    wholesale_df = nordpool_data.copy()
    wholesale_df['value'] = wholesale_df['value'] + data_store_entity.elec_wholesale_offset
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


def remove_agent(some_agent):
    st.session_state.config_data['Agents'].remove(some_agent)


def add_agent(new_agent: Dict[str, Any]):
    if 'agents_added' not in st.session_state:
        st.session_state.agents_added = 1
    else:
        st.session_state.agents_added += 1
    new_agent["Name"] = "NewAgent" + str(st.session_state.agents_added)
    st.session_state.config_data['Agents'].append(new_agent)


def add_building_agent():
    max_random_seed = max([x['RandomSeed'] for x in st.session_state.config_data['Agents']
                           if x['Type'] == "BuildingAgent"])
    add_agent({
        "Type": "BuildingAgent",
        "RandomSeed": max_random_seed + 1,
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
