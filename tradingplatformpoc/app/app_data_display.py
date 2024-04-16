import calendar
import datetime
import logging
from time import strptime
from typing import Any, Dict, List, Optional

import numpy as np

import pandas as pd
from pandas.io.formats.style import Styler

import streamlit as st

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.generate_data.mock_data_utils import get_cooling_cons_key, get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.market.trade import Action, Resource, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.sql.input_data.crud import get_periods_from_db, read_input_column_df_from_db, \
    read_inputs_df_for_agent_creation
from tradingplatformpoc.sql.input_electricity_price.crud import electricity_price_series_from_db
from tradingplatformpoc.sql.level.crud import db_to_viewable_level_df_by_agent
from tradingplatformpoc.sql.mock_data.crud import db_to_mock_data_df, get_mock_data_agent_pairs_in_db
from tradingplatformpoc.sql.results.models import ResultsKey
from tradingplatformpoc.sql.trade.crud import elec_trades_by_external_for_periods_to_df, get_total_import_export
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod

logger = logging.getLogger(__name__)


def get_price_df_when_local_price_inbetween(prices_df: pd.DataFrame, resource: Resource) -> pd.DataFrame:
    """Local price is almost always either equal to the external wholesale or retail price. This method returns the
    subsection of the prices dataframe where the local price is _not_ equal to either of these two."""
    elec_prices = prices_df. \
        loc[prices_df['Resource'].apply(lambda x: x.name) == resource.name]. \
        drop('Resource', axis=1). \
        pivot(index="period", columns="variable")['value']
    local_price_between_external = (elec_prices[app_constants.LOCAL_PRICE_STR]
                                    > elec_prices[app_constants.WHOLESALE_PRICE_STR]
                                    + 0.0001) & (elec_prices[app_constants.LOCAL_PRICE_STR]
                                                 < elec_prices[app_constants.RETAIL_PRICE_STR] - 0.0001)
    return elec_prices.loc[local_price_between_external]


def reconstruct_static_digital_twin(agent_id: str, config: Dict[str, Any], agent_config: Dict[str, Any],
                                    agent_type: str) -> StaticDigitalTwin:
    if agent_type == 'GroceryStoreAgent':
        return reconstruct_grocery_store_static_digital_twin(agent_config)
    elif agent_type == 'BlockAgent':
        return reconstruct_block_agent_static_digital_twin(agent_id, config, agent_config)
    raise NotImplementedError('Method not implemented for agent type ' + agent_type)


def reconstruct_block_agent_static_digital_twin(agent_id: str, config: Dict[str, Any], agent_config: Dict[str, Any]) \
        -> StaticDigitalTwin:
    mock_data_id = list(get_mock_data_agent_pairs_in_db([agent_id], config['MockDataConstants']).keys())[0]
    block_mock_data = db_to_mock_data_df(mock_data_id).to_pandas().set_index('datetime')

    inputs_df = read_inputs_df_for_agent_creation()
    pv_prod_series = calculate_solar_prod(inputs_df['irradiation'], agent_config['PVArea'],
                                          config['AreaInfo']['PVEfficiency'])
    elec_cons_series = block_mock_data[get_elec_cons_key(agent_id)]
    space_heat_cons_series = block_mock_data[get_space_heat_cons_key(agent_id)]
    hot_tap_water_cons_series = block_mock_data[get_hot_tap_water_cons_key(agent_id)]
    cooling_cons_series = block_mock_data[get_cooling_cons_key(agent_id)]

    return StaticDigitalTwin(atemp=agent_config['Atemp'],
                             electricity_usage=elec_cons_series,
                             space_heating_usage=space_heat_cons_series,
                             hot_water_usage=hot_tap_water_cons_series,
                             cooling_usage=cooling_cons_series,
                             electricity_production=pv_prod_series)


def reconstruct_grocery_store_static_digital_twin(agent_config: Dict[str, Any]) -> StaticDigitalTwin:
    inputs_df = read_inputs_df_for_agent_creation()
    pv_prod_series = calculate_solar_prod(inputs_df['irradiation'], agent_config['PVArea'],
                                          agent_config['PVEfficiency'])
    space_heat_prod = inputs_df['coop_space_heating_produced'] if agent_config['SellExcessHeat'] else None

    return StaticDigitalTwin(atemp=agent_config['Atemp'],
                             electricity_usage=inputs_df['coop_electricity_consumed'],
                             space_heating_usage=inputs_df['coop_space_heating_consumed'],
                             hot_water_usage=inputs_df['coop_hot_tap_water_consumed'],
                             electricity_production=pv_prod_series,
                             space_heating_production=space_heat_prod)


# maybe we should move this to simulation_runner/trading_simulator
def construct_combined_price_df(config_data: dict, local_price_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:

    # TODO: Improve this
    elec_pricing: ElectricityPrice = ElectricityPrice(
        elec_wholesale_offset=config_data['AreaInfo']['ExternalElectricityWholesalePriceOffset'],
        elec_tax=config_data['AreaInfo']["ElectricityTax"],
        elec_grid_fee=config_data['AreaInfo']["ElectricityGridFee"],
        elec_tax_internal=config_data['AreaInfo']["ElectricityTaxInternal"],
        elec_grid_fee_internal=config_data['AreaInfo']["ElectricityGridFeeInternal"],
        nordpool_data=electricity_price_series_from_db())

    nordpool_data = elec_pricing.nordpool_data
    nordpool_data.name = 'value'
    nordpool_data = nordpool_data.to_frame().reset_index()
    nordpool_data['Resource'] = Resource.ELECTRICITY
    nordpool_data.rename({'datetime': 'period'}, axis=1, inplace=True)
    nordpool_data['period'] = pd.to_datetime(nordpool_data['period'])
    retail_df = nordpool_data.copy()
    gross_prices = elec_pricing.get_electricity_gross_retail_price_from_nordpool_price(retail_df['value'])
    retail_df['value'] = elec_pricing.get_electricity_net_external_price(gross_prices)
    retail_df['variable'] = app_constants.RETAIL_PRICE_STR
    wholesale_df = nordpool_data.copy()
    wholesale_df['value'] = elec_pricing.get_electricity_wholesale_price_from_nordpool_price(wholesale_df['value'])
    wholesale_df['variable'] = app_constants.WHOLESALE_PRICE_STR
    return pd.concat([local_price_df, retail_df, wholesale_df])


def aggregated_net_elec_import_results_df_split_on_period(job_id: str, period: tuple) -> Optional[pd.DataFrame]:
    """
    Display total import and export for electricity, computed for specified time period.
    @param job_id: Which job to get trades for
    @param period: The time period of interest (a tuple of strings)
    @return: Dataframe split by time period
    """

    start = strptime(period[0], '%b').tm_mon
    end = strptime(period[1], '%b').tm_mon

    all_periods = get_periods_from_db()
    selected_period = [period for period in all_periods if period.month in
                       list(range(start, end + 1, 1))]
  
    period_df = elec_trades_by_external_for_periods_to_df(job_id, selected_period)
    if period_df is not None:
        return avg_weekday_electricity(period_df)
    return None


def avg_weekday_electricity(df: pd.DataFrame) -> pd.DataFrame:
    mean_df = df.groupby(['weekday', 'hour']).agg({'net_import_quantity': [np.mean, np.std]})
    mean_df.columns = ['mean_total_elec', 'std_total_elec']
    mean_df.reset_index(inplace=True)
    mean_df['hour'] = mean_df['hour'].astype('int')
    return mean_df
  

def aggregated_import_and_export_results_df_split_on_mask(job_id: str, periods: List[datetime.datetime],
                                                          mask_col_names: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Display total import and export for electricity and heat, computed for specified subsets.
    @param job_id: Which job to get trades for
    @param periods: What periods to get trades for
    @param mask_col_names: List with strings to display as subset names
    @return: Dict of dataframes displaying total import and export of resources split by the mask
    """

    rows = [Resource.ELECTRICITY, Resource.HIGH_TEMP_HEAT, Resource.LOW_TEMP_HEAT]
    cols = {'Imported': Action.SELL, 'Exported': Action.BUY}

    res_dict = {}
    for col_name, action in cols.items():
        subdict: Dict[str, Dict[str, str]] = {}
        for resource in rows:
            w_mask = "{:.2f} MWh".format(get_total_import_export(job_id, resource, action, periods) / 10**3)
            total = "{:.2f} MWh".format(get_total_import_export(job_id, resource, action) / 10**3)
            subdict[resource.get_display_name()] = {mask_col_names[0]: w_mask, 'Total': total}
        res_dict[col_name] = pd.DataFrame.from_dict(subdict, orient='index')

    return res_dict


def values_by_resource_to_mwh(str_float_dict: Dict[str, float]) -> Dict[str, str]:
    """
    The input dict must fulfill:
    Keys must be resource names (otherwise a RuntimeError will be raised)
    Values should be energy amounts in kWh (since the value will be divided by 1000)
    """
    return {Resource.from_string(k).get_display_name(True): f'{v / 1000:.2f} MWh' for k, v in str_float_dict.items()}


def aggregated_import_and_export_results_df_split_on_period(job_id: str) -> Dict[str, pd.DataFrame]:
    """
    Dict of dataframes displaying total import and export of resources split for January and
    February against rest of the year.
    """
    periods = get_periods_from_db()
    jan_feb_periods = [period for period in periods if period.month in [1, 2]]

    return aggregated_import_and_export_results_df_split_on_mask(job_id, jan_feb_periods, ['Jan-Feb'])


def aggregated_import_and_export_results_df_split_on_temperature(job_id: str) -> Dict[str, pd.DataFrame]:
    """
    Dict of dataframes displaying total import and export of resources split for when the temperature was above
    or below 1 degree Celsius.
    """
    temperature_df = read_input_column_df_from_db('temperature')
    periods = list(temperature_df[temperature_df['temperature'].values >= 1.0].period)
    return aggregated_import_and_export_results_df_split_on_mask(job_id, periods, ['Above'])


# @st.cache_data
def results_by_agent_as_df() -> pd.DataFrame:
    res_by_agents = st.session_state.simulation_results.results_by_agent
    lst = []
    for key, val in res_by_agents.items():
        df = pd.DataFrame.from_dict({k.value: v for (k, v) in val.items()}, orient='index')
        df.rename({0: key}, axis=1, inplace=True)
        lst.append(df)
    dfs = pd.concat(lst, axis=1)
    return dfs


def results_by_agent_as_df_with_highlight(df: pd.DataFrame, agent_chosen_guid: str) -> Styler:
    formatted_df = df.style.set_properties(subset=[agent_chosen_guid], **{'background-color': 'lemonchiffon'}).\
        format('{:.2f}')
    return formatted_df


def build_heat_pump_prod_df(job_id: str, agent_chosen_guid: str, agent_config: dict) -> pd.DataFrame:
    """
    If the agent has a heat pump (booster or normal or both), will return a DataFrame with a DatetimeIndex, and three
    numerical columns:
    'level_high', 'level_low' and 'level_cool'.
    These signify the heat pump production of high-/low-tempered heat and cooling, respectively, in kWh for a given
    hour (a.k.a. kW).
    """
    if agent_config['HeatPumpMaxOutput'] > 0:
        high_heat_prod = db_to_viewable_level_df_by_agent(job_id=job_id, agent_guid=agent_chosen_guid,
                                                          level_type=TradeMetadataKey.HP_HIGH_HEAT_PROD.name)
        low_heat_prod = db_to_viewable_level_df_by_agent(job_id=job_id, agent_guid=agent_chosen_guid,
                                                         level_type=TradeMetadataKey.HP_LOW_HEAT_PROD.name)
        cool_prod = db_to_viewable_level_df_by_agent(job_id=job_id, agent_guid=agent_chosen_guid,
                                                     level_type=TradeMetadataKey.HP_COOL_PROD.name)
        step_1 = pd.merge(high_heat_prod, low_heat_prod, left_index=True, right_index=True, how='outer',
                          suffixes=('_high', '_low')).fillna(0)
        return pd.merge(step_1, cool_prod.rename({'level': 'level_cool'}, axis=1),
                        left_index=True, right_index=True, how='outer').fillna(0)
    if agent_config['BoosterPumpMaxOutput'] > 0:
        high_heat_prod = db_to_viewable_level_df_by_agent(job_id=job_id, agent_guid=agent_chosen_guid,
                                                          level_type=TradeMetadataKey.HP_HIGH_HEAT_PROD.name)
        return high_heat_prod.rename({'level': 'level_high'}, axis=1)
    else:
        return pd.DataFrame()


def get_bites_dfs(job_id: str, agent_chosen_guid: str) -> Dict[TradeMetadataKey, pd.DataFrame]:
    """Constructs a dict, with a dataframe for each type of BITES-related field."""
    keys = [TradeMetadataKey.SHALLOW_STORAGE_ABS,
            TradeMetadataKey.DEEP_STORAGE_ABS,
            TradeMetadataKey.SHALLOW_CHARGE,
            TradeMetadataKey.FLOW_SHALLOW_TO_DEEP,
            TradeMetadataKey.SHALLOW_LOSS,
            TradeMetadataKey.DEEP_LOSS]
    return get_dfs_by_tmk(agent_chosen_guid, job_id, keys)


def get_storage_dfs(job_id: str, agent_chosen_guid: str) -> Dict[TradeMetadataKey, pd.DataFrame]:
    """Constructs a dict, with a dataframe for each type of storage."""
    keys = [TradeMetadataKey.BATTERY_LEVEL,
            TradeMetadataKey.SHALLOW_STORAGE_REL,
            TradeMetadataKey.DEEP_STORAGE_REL,
            TradeMetadataKey.ACC_TANK_LEVEL]
    return get_dfs_by_tmk(agent_chosen_guid, job_id, keys)


def get_dfs_by_tmk(agent_chosen_guid, job_id, keys):
    """Constructs a dict, with a dataframe for each TradeMetadataKey."""
    my_dict: Dict[TradeMetadataKey, pd.DataFrame] = {}
    for tmk in keys:
        df = db_to_viewable_level_df_by_agent(job_id=job_id, agent_guid=agent_chosen_guid, level_type=tmk.name)
        if not df.empty:
            my_dict[tmk] = df
    return my_dict


def combine_trades_dfs(agg_buy_trades: Optional[pd.DataFrame], agg_sell_trades: Optional[pd.DataFrame]) \
        -> Optional[pd.DataFrame]:
    """Aims to merge two pd.DataFrames, if they are present."""
    if agg_buy_trades is not None and agg_sell_trades is not None:
        return agg_buy_trades.merge(agg_sell_trades, on='Agent', how='outer')
    elif agg_buy_trades is not None:
        return agg_buy_trades
    elif agg_sell_trades is not None:
        return agg_sell_trades
    else:
        return None


def build_leaderboard_df(list_of_dicts: List[dict]) -> pd.DataFrame:
    df_to_display = pd.DataFrame.from_records(list_of_dicts, index='Config ID')
    # Some pre-calculated results are saved as Dicts, with resource-names as keys. We expand these here:
    for col in df_to_display.columns:
        if isinstance(df_to_display[col][0], dict):
            for key in df_to_display[col][0].keys():
                if Resource.is_resource_name(key):
                    new_col_name = ResultsKey.format_results_key_name(col, Resource.from_string(key))
                    df_to_display[new_col_name] = df_to_display[col].apply(lambda d, k=key: d[k])
    wanted_columns = ['Description',
                      ResultsKey.NET_ENERGY_SPEND,
                      ResultsKey.format_results_key_name(ResultsKey.SUM_NET_IMPORT, Resource.ELECTRICITY),
                      ResultsKey.format_results_key_name(ResultsKey.SUM_NET_IMPORT, Resource.HIGH_TEMP_HEAT),
                      ResultsKey.format_results_key_name(ResultsKey.MAX_NET_IMPORT, Resource.ELECTRICITY),
                      ResultsKey.format_results_key_name(ResultsKey.MAX_NET_IMPORT, Resource.HIGH_TEMP_HEAT),
                      ResultsKey.format_results_key_name(ResultsKey.LOCALLY_PRODUCED_RESOURCES, Resource.ELECTRICITY),
                      ResultsKey.format_results_key_name(ResultsKey.LOCALLY_PRODUCED_RESOURCES,
                                                         Resource.HIGH_TEMP_HEAT),
                      ResultsKey.format_results_key_name(ResultsKey.LOCALLY_PRODUCED_RESOURCES, Resource.LOW_TEMP_HEAT),
                      ResultsKey.TAX_PAID,
                      ResultsKey.GRID_FEES_PAID,
                      ResultsKey.format_results_key_name(ResultsKey.SUM_IMPORT_BELOW_1_C, Resource.HIGH_TEMP_HEAT),
                      ResultsKey.format_results_key_name(ResultsKey.SUM_IMPORT_JAN_FEB, Resource.HIGH_TEMP_HEAT),
                      ResultsKey.HEAT_DUMPED,
                      ResultsKey.COOL_DUMPED]

    for wanted_column in wanted_columns:
        if wanted_column not in df_to_display.columns:
            # May happen for runs that were made using a previous app version, for example
            logger.warning("Column '{}' not found in pre-calculated results".format(wanted_column))
            df_to_display[wanted_column] = None
    return df_to_display[wanted_columns].round(decimals=0)


def build_monthly_stats_df(pre_calculated_results: Dict[str, Any], resource: Resource) -> pd.DataFrame:
    columns = [ResultsKey.MONTHLY_MAX_NET_IMPORT,
               ResultsKey.MONTHLY_SUM_NET_IMPORT,
               ResultsKey.MONTHLY_SUM_IMPORT,
               ResultsKey.MONTHLY_SUM_EXPORT]
    df = pd.DataFrame([pre_calculated_results[key][resource.name] for key in columns]).transpose()
    # Format column names.
    df.columns = [ResultsKey.format_results_key_name(key, resource) for key in columns]
    if (df[ResultsKey.format_results_key_name(ResultsKey.MONTHLY_SUM_NET_IMPORT, resource)]
            == df[ResultsKey.format_results_key_name(ResultsKey.MONTHLY_SUM_IMPORT, resource)]).all():
        # Will happen if the LEC cannot export the given resource
        df.drop(labels=[ResultsKey.format_results_key_name(ResultsKey.MONTHLY_SUM_NET_IMPORT, resource),
                        ResultsKey.format_results_key_name(ResultsKey.MONTHLY_SUM_EXPORT, resource)],
                axis=1, inplace=True)

    # Some formatting: First, change indices to show month names instead of integers
    df.index = df.index.map(lambda x: calendar.month_name[int(x)])
    # Now, the 'monthly' bit in column headers is superfluous when listed in a table like this
    df.columns = [c.replace('monthly ', '') for c in df.columns]
    # Finally, decrease the number of decimals a little (defaults to 4)
    df = df.style.format(precision=2)
    # noinspection PyTypeChecker
    return df
