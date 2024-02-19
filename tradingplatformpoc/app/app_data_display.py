
import datetime
from time import strptime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import pandas as pd
from pandas.io.formats.style import Styler

import streamlit as st

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.generate_data.mock_data_utils import get_cooling_cons_key, get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.sql.electricity_price.crud import db_to_electricity_price_dict
from tradingplatformpoc.sql.extra_cost.crud import db_to_aggregated_extra_costs_by_agent
from tradingplatformpoc.sql.heating_price.crud import db_to_heating_price_dict
from tradingplatformpoc.sql.input_data.crud import get_periods_from_db, read_input_column_df_from_db, \
    read_inputs_df_for_agent_creation
from tradingplatformpoc.sql.input_electricity_price.crud import electricity_price_series_from_db
from tradingplatformpoc.sql.level.crud import db_to_viewable_level_df_by_agent
from tradingplatformpoc.sql.mock_data.crud import db_to_mock_data_df, get_mock_data_agent_pairs_in_db
from tradingplatformpoc.sql.trade.crud import db_to_trades_by_agent_and_resource_action, \
    elec_trades_by_external_for_periods_to_df, get_total_import_export, get_total_traded_for_agent
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod


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


def reconstruct_static_digital_twin(agent_id: str, mock_data_constants: Dict[str, Any],
                                    pv_area: float, pv_efficiency: float) -> StaticDigitalTwin:
    mock_data_id = list(get_mock_data_agent_pairs_in_db([agent_id], mock_data_constants).keys())[0]
    block_mock_data = db_to_mock_data_df(mock_data_id).to_pandas().set_index('datetime')

    inputs_df = read_inputs_df_for_agent_creation()
    pv_prod_series = calculate_solar_prod(inputs_df['irradiation'], pv_area, pv_efficiency)
    elec_cons_series = block_mock_data[get_elec_cons_key(agent_id)]
    space_heat_cons_series = block_mock_data[get_space_heat_cons_key(agent_id)]
    hot_tap_water_cons_series = block_mock_data[get_hot_tap_water_cons_key(agent_id)]
    cooling_cons_series = block_mock_data[get_cooling_cons_key(agent_id)]

    return StaticDigitalTwin(electricity_usage=elec_cons_series,
                             space_heating_usage=space_heat_cons_series,
                             hot_water_usage=hot_tap_water_cons_series,
                             electricity_production=pv_prod_series,
                             cooling_usage=cooling_cons_series)


# maybe we should move this to simulation_runner/trading_simulator
def construct_combined_price_df(local_price_df: pd.DataFrame, config_data: dict) -> pd.DataFrame:

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


def aggregated_taxes_and_fees_results_df(tax_paid: float, grid_fees_paid_on_internal_trades: float) -> pd.DataFrame:
    """
    @return: Dataframe displaying total taxes and fees.
    """
    return pd.DataFrame(index=["Taxes paid", "Grid fees paid on internal trades"],
                        columns=['Total'],
                        data=["{:.2f} SEK".format(tax_paid),
                              "{:.2f} SEK".format(grid_fees_paid_on_internal_trades)
                              ])


def aggregated_net_elec_import_results_df_split_on_period(job_id: str, period: tuple) -> pd.DataFrame:
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
    return avg_weekday_electricity(period_df)


def avg_weekday_electricity(df: pd.DataFrame) -> pd.DataFrame:

    mean_df = df.groupby(['weekday', 'hour']).agg({'net_import_quantity': [np.mean, np.std]})
    mean_df.columns = ['mean_total_elec', 'std_total_elec']
    mean_df.reset_index(inplace=True)
    mean_df['hour'] = mean_df['hour'].astype('int')
    return mean_df
  

def aggregated_import_and_export_results_df_split_on_mask(job_id: str, periods: List[datetime.datetime],
                                                          mask_colnames: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Display total import and export for electricity and heat, computed for specified subsets.
    @param job_id: Which job to get trades for
    @param periods: What periods to get trades for
    @param mask_colnames: List with strings to display as subset names
    @return: Dict of dataframes displaying total import and export of resources split by the mask
    """

    rows = {'Electricity': Resource.ELECTRICITY, 'Heating': Resource.HEATING}
    cols = {'Imported': Action.SELL, 'Exported': Action.BUY}

    res_dict = {}
    for colname, action in cols.items():
        subdict = {}
        for rowname, resource in rows.items():
            w_mask = "{:.2f} MWh".format(get_total_import_export(job_id, resource, action, periods) / 10**3)
            total = "{:.2f} MWh".format(get_total_import_export(job_id, resource, action) / 10**3)
            subdict[rowname] = {mask_colnames[0]: w_mask, 'Total': total}
        res_dict[colname] = pd.DataFrame.from_dict(subdict, orient='index')

    return res_dict


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


def resource_dict_to_display_df(number_by_resource: Dict[str, float], scale_factor: float, unit: str, col_header: str) \
        -> pd.DataFrame:
    """
    Computing total amount of locally produced resources.
    """
    data_list = []
    index_list = []
    for (resource, number) in number_by_resource.items():
        data_list.append("{:.2f} {}".format(number * scale_factor, unit))
        index_list.append(resource)
    return pd.DataFrame(data=data_list, index=index_list, columns=[col_header])


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


def get_savings_vs_only_external_buy_heat(job_id: str, agent_guid: str) -> float:
    buy_trades = db_to_trades_by_agent_and_resource_action(job_id, agent_guid, Resource.HEATING, Action.BUY)
    retail_prices = db_to_heating_price_dict(job_id, "exact_retail_price")
    return sum([trade.quantity_pre_loss * (retail_prices[(trade.year, trade.month)] - trade.price)
                for trade in buy_trades])


def get_savings_vs_only_external_sell_heat(job_id: str, agent_guid: str) -> float:
    sell_trades = db_to_trades_by_agent_and_resource_action(job_id, agent_guid, Resource.HEATING, Action.SELL)
    wholesale_prices = db_to_heating_price_dict(job_id, "exact_wholesale_price")
    return sum([trade.quantity_post_loss * (trade.price - wholesale_prices[(trade.year, trade.month)])
                for trade in sell_trades])


def get_savings_vs_only_external_buy_elec(job_id: str, agent_guid: str) -> float:
    buy_trades = db_to_trades_by_agent_and_resource_action(job_id, agent_guid, Resource.ELECTRICITY, Action.BUY)
    retail_prices = db_to_electricity_price_dict(job_id, "retail_price")
    return sum([trade.quantity_pre_loss * (retail_prices[trade.period] - trade.price)
                for trade in buy_trades])


def get_savings_vs_only_external_sell_elec(job_id: str, agent_guid: str) -> float:
    sell_trades = db_to_trades_by_agent_and_resource_action(job_id, agent_guid, Resource.ELECTRICITY, Action.SELL)
    wholesale_prices = db_to_electricity_price_dict(job_id, "wholesale_price")
    return sum([trade.quantity_post_loss * (trade.price - wholesale_prices[trade.period])
                for trade in sell_trades])


def get_savings_vs_only_external_buy(job_id: str, agent_guid: str) -> Tuple[float, float]:

    extra_costs_for_bad_bids, extra_costs_for_heat_cost_discr = \
        db_to_aggregated_extra_costs_by_agent(job_id, agent_guid)
    
    # Saving by using local market, before taking penalties into account [SEK]
    total_saved = get_savings_vs_only_external_buy_heat(job_id, agent_guid) \
        + get_savings_vs_only_external_buy_elec(job_id, agent_guid) \
        + get_savings_vs_only_external_sell_heat(job_id, agent_guid) \
        + get_savings_vs_only_external_sell_elec(job_id, agent_guid) \
        - extra_costs_for_heat_cost_discr
    # TODO: This is bugged somehow.
    #  Test running simulations with only 1 grocery store agent, then total_saved should be 0, but isn't
    return total_saved, extra_costs_for_bad_bids


def get_total_profit_net(job_id: str, agent_guid: str) -> float:
    return get_total_traded_for_agent(job_id, agent_guid, Action.SELL) \
        - get_total_traded_for_agent(job_id, agent_guid, Action.BUY)


def build_heat_pump_levels_df(job_id: str, agent_chosen_guid: str, agent_config: dict) -> pd.DataFrame:
    if agent_config['HeatPumpMaxOutput'] > 0:
        return db_to_viewable_level_df_by_agent(
            job_id=job_id,
            agent_guid=agent_chosen_guid,
            level_type=TradeMetadataKey.HEAT_PUMP_WORKLOAD.name)
    else:
        return pd.DataFrame()


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
