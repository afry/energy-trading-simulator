import json
from typing import Any, Dict

import altair as alt

import numpy as np

import pandas as pd

import streamlit as st

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.bid import Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.trading_platform_utils import ALL_AGENT_TYPES, ALL_IMPLEMENTED_RESOURCES_STR, get_if_exists_else


def get_price_df_when_local_price_inbetween(prices_df: pd.DataFrame, resource: Resource) -> pd.DataFrame:
    """Local price is almost always either equal to the external wholesale or retail price. This method returns the
    subsection of the prices dataframe where the local price is _not_ equal to either of these two."""
    elec_prices = prices_df.\
        loc[prices_df['Resource'] == resource].\
        drop('Resource', axis=1).\
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
    clearing_prices_df.variable = app_constants.LOCAL_PRICE_STR

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
    retail_df['variable'] = app_constants.RETAIL_PRICE_STR
    wholesale_df = nordpool_data.copy()
    wholesale_df['value'] = wholesale_df['value'] + data_store_entity.elec_wholesale_offset
    wholesale_df['variable'] = app_constants.WHOLESALE_PRICE_STR

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


def remove_all_building_agents():
    st.session_state.config_data['Agents'] = [agent for agent in st.session_state.config_data['Agents']
                                              if agent['Type'] != 'BuildingAgent']


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


def agent_inputs(agent):
    """Contains input fields needed to define an agent."""
    agent['Name'] = st.text_input('Name', value=agent['Name'])
    agent['Type'] = st.selectbox('Type', options=ALL_AGENT_TYPES,
                                 key='TypeSelectBox' + agent['Name'],
                                 index=ALL_AGENT_TYPES.index(agent['Type']))
    if agent['Type'] == 'BuildingAgent':
        agent['RandomSeed'] = int(st.number_input(
            'Random seed',
            value=int(agent['RandomSeed']),
            help=app_constants.RANDOM_SEED_HELP_TEXT,
            key='RandomSeed' + agent['Name']
        ))
        agent['GrossFloorArea'] = st.number_input(
            'Gross floor area (sqm)', min_value=0.0,
            value=float(agent['GrossFloorArea']),
            help=app_constants.GROSS_FLOOR_AREA_HELP_TEXT,
            key='GrossFloorArea' + agent['Name']
        )
        agent['FractionCommercial'] = st.number_input(
            'Fraction commercial', min_value=0.0, max_value=1.0,
            value=get_if_exists_else(agent, 'FractionCommercial', 0.0),
            help=app_constants.FRACTION_COMMERCIAL_HELP_TEXT,
            key='FractionCommercial' + agent['Name']
        )
        agent['FractionSchool'] = st.number_input(
            'Fraction school', min_value=0.0, max_value=1.0,
            value=get_if_exists_else(agent, 'FractionSchool', 0.0),
            help=app_constants.FRACTION_SCHOOL_HELP_TEXT,
            key='FractionSchool' + agent['Name']
        )
    if agent['Type'] in ['StorageAgent', 'GridAgent']:
        agent['Resource'] = st.selectbox('Resource', options=ALL_IMPLEMENTED_RESOURCES_STR,
                                         key='ResourceSelectBox' + agent['Name'],
                                         index=ALL_IMPLEMENTED_RESOURCES_STR.index(agent['Resource']))
    if agent['Type'] == 'StorageAgent':
        agent['Capacity'] = st.number_input(
            'Capacity', min_value=0.0, step=1.0,
            value=float(agent['Capacity']),
            help=app_constants.CAPACITY_HELP_TEXT,
            key='Capacity' + agent['Name']
        )
        agent['ChargeRate'] = st.number_input(
            'Charge rate', min_value=0.01, max_value=10.0,
            value=float(agent['ChargeRate']),
            help=app_constants.CHARGE_RATE_HELP_TEXT,
            key='ChargeRate' + agent['Name']
        )
        agent['RoundTripEfficiency'] = st.number_input(
            'Round-trip efficiency', min_value=0.01, max_value=1.0,
            value=float(agent['RoundTripEfficiency']),
            help=app_constants.ROUND_TRIP_EFFICIENCY_HELP_TEXT,
            key='RoundTripEfficiency' + agent['Name']
        )
        agent['NHoursBack'] = int(st.number_input(
            '\'N hours back\'', min_value=1, max_value=8760,
            value=int(agent['NHoursBack']),
            help=app_constants.N_HOURS_BACK_HELP_TEXT,
            key='NHoursBack' + agent['Name']
        ))
        agent['BuyPricePercentile'] = st.number_input(
            '\'Buy-price percentile\'', min_value=0.0, max_value=100.0, step=1.0,
            value=float(agent['BuyPricePercentile']),
            help=app_constants.BUY_PERC_HELP_TEXT,
            key='BuyPricePercentile' + agent['Name']
        )
        agent['SellPricePercentile'] = st.number_input(
            '\'Sell-price percentile\'', min_value=0.0, max_value=100.0, step=1.0,
            value=float(agent['SellPricePercentile']),
            help=app_constants.SELL_PERC_HELP_TEXT,
            key='SellPricePercentile' + agent['Name']
        )
        agent['DischargeRate'] = st.number_input(
            'Discharge rate', min_value=0.01, max_value=10.0,
            value=float(get_if_exists_else(agent, 'DischargeRate', agent['ChargeRate'])),
            help=app_constants.DISCHARGE_RATE_HELP_TEXT,
            key='DischargeRate' + agent['Name']
        )
    if agent['Type'] in ['BuildingAgent', 'PVAgent', 'GroceryStoreAgent']:
        agent['PVArea'] = st.number_input(
            'PV area (sqm)', min_value=0.0, format='%.1f', step=1.0,
            value=float(get_if_exists_else(agent, 'PVArea', 0.0)),
            help=app_constants.PV_AREA_HELP_TEXT,
            key='PVArea' + agent['Name']
        )
        agent['PVEfficiency'] = st.number_input(
            'PV efficiency', min_value=0.01, max_value=0.99, format='%.3f',
            value=get_if_exists_else(agent, 'PVEfficiency',
                                     st.session_state.config_data['AreaInfo']['DefaultPVEfficiency']),
            help=app_constants.PV_EFFICIENCY_HELP_TEXT,
            key='PVEfficiency' + agent['Name']
        )
    if agent['Type'] == 'GridAgent':
        agent['TransferRate'] = st.number_input(
            'Transfer rate', min_value=0.0, step=10.0,
            value=float(agent['TransferRate']),
            help=app_constants.TRANSFER_RATE_HELP_TEXT,
            key='TransferRate' + agent['Name']
        )
    else:
        st.button('Remove agent', key='RemoveButton' + agent['Name'], on_click=remove_agent, args=(agent,))
