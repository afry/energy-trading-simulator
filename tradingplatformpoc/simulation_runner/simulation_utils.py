import datetime
import logging
import pickle
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Collection, Dict, List, Tuple, Union

import pandas as pd

from sqlalchemy import delete, select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.generate_data import generate_mock_data
from tradingplatformpoc.generate_data.mock_data_generation_functions import MockDataKey, get_all_building_agents
from tradingplatformpoc.market.bid import Action, GrossBid, NetBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Market, Trade, TradeMetadataKey
from tradingplatformpoc.sql.bid.models import Bid as TableBid
from tradingplatformpoc.sql.trade.models import Trade as TableTrade
from tradingplatformpoc.trading_platform_utils import add_to_nested_dict

logger = logging.getLogger(__name__)


def net_bids_from_gross_bids(gross_bids: List[GrossBid], data_store_entity: DataStore) -> List[NetBid]:
    """
    Add in internal tax and internal grid fee for internal SELL bids (for electricity, heating is not taxed).
    Note: External electricity bids already have grid fee
    """
    net_bids: List[NetBid] = []
    for gross_bid in gross_bids:
        if gross_bid.action == Action.SELL and gross_bid.resource == Resource.ELECTRICITY:
            if gross_bid.by_external:
                net_price = data_store_entity.get_electricity_net_external_price(gross_bid.price)
                net_bids.append(NetBid.from_gross_bid(gross_bid, net_price))
            else:
                net_price = data_store_entity.get_electricity_net_internal_price(gross_bid.price)
                net_bids.append(NetBid.from_gross_bid(gross_bid, net_price))
        else:
            net_bids.append(NetBid.from_gross_bid(gross_bid, gross_bid.price))
    return net_bids


def go_through_trades_metadata(metadata: Dict[TradeMetadataKey, Any], period: datetime.datetime, agent_guid: str,
                               heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]],
                               storage_levels_dict: Dict[str, Dict[datetime.datetime, float]]):
    """
    The agent may want to send some metadata along with its trade, to the simulation runner. Any such metadata is dealt
    with here.
    """
    for metadata_key in metadata:
        if metadata_key == TradeMetadataKey.STORAGE_LEVEL:
            capacity_for_agent = metadata[metadata_key]
            add_to_nested_dict(storage_levels_dict, agent_guid, period, capacity_for_agent)
        elif metadata_key == TradeMetadataKey.HEAT_PUMP_WORKLOAD:
            current_heat_pump_level = metadata[metadata_key]
            add_to_nested_dict(heat_pump_levels_dict, agent_guid, period, current_heat_pump_level)
        else:
            logger.info('Encountered unexpected metadata! Key: {}, Value: {}'.
                        format(metadata_key, metadata[metadata_key]))


def get_external_heating_prices(data_store_entity: DataStore, trading_periods: Collection[datetime.datetime]) -> \
        Tuple[Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float]]:
    exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    estimated_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    estimated_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    for (year, month) in set([(dt.year, dt.month) for dt in trading_periods]):
        first_day_of_month = datetime.datetime(year, month, 1)  # Which day it is doesn't matter
        exact_retail_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_exact_retail_price(first_day_of_month, Resource.HEATING, include_tax=True)
        exact_wholesale_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_exact_wholesale_price(first_day_of_month, Resource.HEATING)
        estimated_retail_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_estimated_retail_price(first_day_of_month, Resource.HEATING, include_tax=True)
        estimated_wholesale_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_estimated_wholesale_price(first_day_of_month, Resource.HEATING)
    return estimated_retail_heating_prices_by_year_and_month, \
        estimated_wholesale_heating_prices_by_year_and_month, \
        exact_retail_heating_prices_by_year_and_month, \
        exact_wholesale_heating_prices_by_year_and_month


def get_generated_mock_data(config_data: dict, mock_datas_pickle_path: str) -> pd.DataFrame:
    """
    Loads the dict stored in MOCK_DATAS_PICKLE, checks if it contains a key which is identical to the set of building
    agents specified in config_data. If it isn't, throws an error. If it is, it returns the value for that key in the
    dictionary.
    @param config_data: A dictionary specifying agents etc
    @param mock_datas_pickle_path: Path to pickle file where dict with mock data is saved
    @return: A pd.DataFrame containing mock data for building agents
    """
    with open(mock_datas_pickle_path, 'rb') as f:
        all_data_sets = pickle.load(f)
    building_agents, total_gross_floor_area = get_all_building_agents(config_data["Agents"])
    mock_data_key = MockDataKey(frozenset(building_agents), frozenset(config_data["MockDataConstants"].items()))
    if mock_data_key not in all_data_sets:
        logger.info("No mock data found for this configuration. Running mock data generation.")
        all_data_sets = generate_mock_data.run(config_data)
        logger.info("Finished mock data generation.")
    return all_data_sets[mock_data_key].to_pandas().set_index('datetime')


def get_quantity_heating_sold_by_external_grid(external_trades: List[Trade]) -> float:
    return sum([x.quantity_post_loss for x in external_trades if
                (x.resource == Resource.HEATING) & (x.action == Action.SELL)])


def construct_df_from_datetime_dict(some_dict: Union[Dict[datetime.datetime, Collection[NetBidWithAcceptanceStatus]],
                                                     Dict[datetime.datetime, Collection[Trade]]]) \
        -> pd.DataFrame:
    """
    Streamlit likes to deal with pd.DataFrames, so we'll save data in that format.
    """
    logger.info('Constructing dataframe from datetime dict')
    return pd.DataFrame([x.to_dict_with_period(period) for period, some_collection in some_dict.items()
                         for x in some_collection])


def fields_to_strings(df, col):
    for val in pd.unique(df[col]):
        df.loc[df[col] == val, col] = val.name


def save_to_db(data: str, job_id: str, df: pd.DataFrame, keys_to_categories: List[str],
               session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    for key in keys_to_categories:
        fields_to_strings(df, key)
    df['job_id'] = job_id
    if data == 'trades':
        objects = [TableTrade(**trade_row) for _i, trade_row in df.iterrows()]
    elif data == 'bids':
        objects = [TableBid(**bid_row) for _i, bid_row in df.iterrows()]
    with session_generator() as db:
        db.bulk_save_objects(objects)
        db.commit()


def delete_from_db(job_id: str, table_name: str,
                   session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        if table_name == 'Trade':
            db.execute(delete(TableTrade).where(TableTrade.job_id == job_id))
        elif table_name == 'Bid':
            db.execute(delete(TableBid).where(TableBid.job_id == job_id))
        db.commit()


def bids_to_db(trades_dict: Dict[datetime.datetime, Collection[NetBidWithAcceptanceStatus]], job_id: str):
    objects = [TableBid(period=period,
                        job_id=job_id,
                        source=x.source,
                        by_external=x.by_external,
                        action=x.action.name,
                        resource=x.resource.name,
                        quantity=x.quantity,
                        price=x.price,
                        accepted_quantity=x.accepted_quantity)
               for period, some_collection in trades_dict.items() for x in some_collection]
    bulk_insert(objects)
        

def trades_to_db(bids_dict: Dict[datetime.datetime, Collection[Trade]], job_id: str):
    objects = [TableTrade(period=period,
                          job_id=job_id,
                          source=x.source,
                          by_external=x.by_external,
                          action=x.action.name,
                          resource=x.resource.name,
                          quantity_pre_loss=x.quantity_pre_loss,
                          quantity_post_loss=x.quantity_post_loss,
                          price=x.price,
                          market=x.market.name,
                          tax_paid=x.tax_paid,
                          grid_fee_paid=x.grid_fee_paid)
               for period, some_collection in bids_dict.items() for x in some_collection]
    bulk_insert(objects)


def bulk_insert(objects: list,
                session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        db.bulk_save_objects(objects)
        db.commit()


def db_to_trade_df(job_id: str,
                   session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) -> pd.DataFrame:
    with session_generator() as db:
        trades = db.execute(select(TableTrade).where(TableTrade.job_id == job_id)).all()
        return pd.DataFrame.from_records([{'period': trade.period,
                                           'action': Action[trade.action],
                                           'resource': Resource[trade.resource],
                                           'quantity_pre_loss': trade.quantity_pre_loss,
                                           'quantity_post_loss': trade.quantity_post_loss,
                                           'price': trade.price,
                                           'source': trade.source,
                                           'by_external': trade.by_external,
                                           'market': Market[trade.market],
                                           'tax_paid': trade.tax_paid,
                                           'grid_fee_paid': trade.grid_fee_paid
                                           } for (trade, ) in trades])


def db_to_bid_df(job_id: str,
                 session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) -> pd.DataFrame:
    with session_generator() as db:
        bids = db.execute(select(TableBid).where(TableBid.job_id == job_id)).all()
        return pd.DataFrame.from_records([{'period': bid.period,
                                           'action': Action[bid.action],
                                           'resource': Resource[bid.resource],
                                           'quantity': bid.quantity,
                                           'price': bid.price,
                                           'source': bid.source,
                                           'by_external': bid.by_external,
                                           'accepted_quantity': bid.quantity
                                           } for (bid, ) in bids])
