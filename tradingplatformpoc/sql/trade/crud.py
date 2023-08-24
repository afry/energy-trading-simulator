import datetime
import itertools
import operator
from contextlib import _GeneratorContextManager
from typing import Callable, Collection, Dict, Tuple

import pandas as pd

from sqlalchemy import func, select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Trade
from tradingplatformpoc.sql.trade.models import Trade as TableTrade


def heat_trades_from_db_for_periods(trading_periods, job_id: str,
                                    session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope)\
        -> Dict[datetime.datetime, Dict]:
    with session_generator() as db:
        trades_for_month = db.execute(select(TableTrade.period.label('period'),
                                             TableTrade.action.label('action').label('action'),
                                             TableTrade.quantity_pre_loss.label('quantity_pre_loss'),
                                             TableTrade.quantity_post_loss.label('quantity_post_loss'),
                                             TableTrade.source.label('source'),
                                             TableTrade.by_external.label('by_external'),
                                             TableTrade.market.label('market'))
                                      .where((TableTrade.job_id == job_id)
                                             & (TableTrade.period >= trading_periods.min())
                                             & (TableTrade.period <= trading_periods.max())
                                             & (TableTrade.resource == 'HEATING'))
                                      .order_by(TableTrade.period)).all()

        return dict((period, list(vals)) for period, vals in
                    itertools.groupby(trades_for_month, operator.itemgetter(0)))


def db_to_trade_df(job_id: str,
                   session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) -> pd.DataFrame:
    with session_generator() as db:
        trades = db.execute(select(TableTrade).where(TableTrade.job_id == job_id)).all()
        return pd.DataFrame.from_records([{'period': trade.period,
                                           'action': trade.action,
                                           'resource': trade.resource,
                                           'quantity_pre_loss': trade.quantity_pre_loss,
                                           'quantity_post_loss': trade.quantity_post_loss,
                                           'price': trade.price,
                                           'source': trade.source,
                                           'by_external': trade.by_external,
                                           'market': trade.market,
                                           'tax_paid': trade.tax_paid,
                                           'grid_fee_paid': trade.grid_fee_paid
                                           } for (trade, ) in trades])


def trades_to_db_objects(bids_dict: Dict[datetime.datetime, Collection[Trade]], job_id: str):
    objects = [TableTrade(period=period,
                          job_id=job_id,
                          source=x.source,
                          by_external=x.by_external,
                          action=x.action,
                          resource=x.resource,
                          quantity_pre_loss=x.quantity_pre_loss,
                          quantity_post_loss=x.quantity_post_loss,
                          price=x.price,
                          market=x.market,
                          tax_paid=x.tax_paid,
                          grid_fee_paid=x.grid_fee_paid)
               for period, some_collection in bids_dict.items() for x in some_collection]
    return objects


def db_to_aggregated_buy_trades_by_agent(job_id: str, resource: Resource,
                                         session_generator: Callable[[], _GeneratorContextManager[Session]]
                                         = session_scope):
    '''Fetches aggregated buy trades data from database for specified agent (source).'''
    with session_generator() as db:
        res = db.query(
            TableTrade.source.label('Agent'),
            func.sum(TableTrade.quantity_pre_loss).label('Total quantity bought [kWh]'),
            func.sum(TableTrade.total_bought_for).label('Total amount bought for [SEK]'),
        ).filter(TableTrade.job_id == job_id,
                 TableTrade.action == Action.SELL,
                 TableTrade.resource == resource)\
         .group_by(TableTrade.source, TableTrade.resource).all()

        df = pd.DataFrame(res).set_index('Agent')
        df['Average buy price [SEK/kWh]'] = df['Total amount bought for [SEK]'] / df['Total quantity bought [kWh]']
        return df
    

def db_to_aggregated_sell_trades_by_agent(job_id: str, resource: Resource,
                                          session_generator: Callable[[], _GeneratorContextManager[Session]]
                                          = session_scope):
    '''Fetches aggregated sell trades data from database for specified agent (source).'''
    with session_generator() as db:
        res = db.query(
            TableTrade.source.label('Agent'),
            func.sum(TableTrade.quantity_post_loss).label('Total quantity sold [kWh]'),
            func.sum(TableTrade.total_sold_for).label('Total amount sold for [SEK]'),
        ).filter(TableTrade.job_id == job_id,
                 TableTrade.action == Action.BUY,
                 TableTrade.resource == resource)\
         .group_by(TableTrade.source, TableTrade.resource).all()

        df = pd.DataFrame(res).set_index('Agent')
        df['Average sell price [SEK/kWh]'] = df['Total amount sold for [SEK]'] / df['Total quantity sold [kWh]']
        return df


def db_to_trades_by_agent(source: str, job_id: str,
                          session_generator: Callable[[], _GeneratorContextManager[Session]]
                          = session_scope) -> pd.DataFrame:
    # Fetches trades data from database for specified agent (source).
    with session_generator() as db:
        trades = db.execute(select(TableTrade.period.label('period'),
                                   TableTrade.action.label('action').label('action'),
                                   TableTrade.resource.label('resource'),
                                   TableTrade.quantity_pre_loss.label('quantity_pre_loss'),
                                   TableTrade.quantity_post_loss.label('quantity_post_loss'),
                                   TableTrade.price.label('price'))
                            .where((TableTrade.job_id == job_id) & (TableTrade.source == source))).all()
        return trades
    

def db_to_viewable_trade_df_by_agent(job_id: str, agent_guid: str,
                                     session_generator: Callable[[], _GeneratorContextManager[Session]]
                                     = session_scope):
    """
    Fetches trades data from database for specified agent (agent_guid) and changes to a df.
    """
    with session_generator() as db:
        trades = db.query(TableTrade).filter(TableTrade.source == agent_guid, TableTrade.job_id == job_id).all()

        if len(trades) > 0:
            return pd.DataFrame.from_records([{'period': trade.period,
                                               'action': trade.action.name,
                                               'resource': trade.resource.name,
                                               'market': trade.market.name,
                                               'quantity_pre_loss': trade.quantity_pre_loss,
                                               'quantity_post_loss': trade.quantity_post_loss,
                                               'price': trade.price,
                                               'tax_paid': trade.tax_paid,
                                               'grid_fee_paid': trade.grid_fee_paid
                                               } for trade in trades], index='period')
        else:
            return pd.DataFrame(columns=['period', 'action', 'resource', 'market', 'quantity_pre_loss',
                                         'quantity_post_loss', 'price', 'tax_paid', 'grid_fee_paid'])


def get_total_tax_paid(job_id: str,
                       session_generator: Callable[[], _GeneratorContextManager[Session]]
                       = session_scope) -> Tuple[float, float]:
    with session_generator() as db:
        res = db.query(
            func.sum(TableTrade.tax_paid_for_quantity).label('sum_tax_paid_for_quantities'),
        ).filter(TableTrade.action == Action.SELL, TableTrade.job_id == job_id).first()

        return res.sum_tax_paid_for_quantities if res.sum_tax_paid_for_quantities is not None else 0.0


def get_total_grid_fee_paid_on_internal_trades(job_id: str,
                                               session_generator: Callable[[], _GeneratorContextManager[Session]]
                                               = session_scope) -> Tuple[float, float]:
    with session_generator() as db:
        res = db.query(
            func.sum(TableTrade.grid_fee_paid_for_quantity).label('sum_grid_fee_paid_for_quantities'),
        ).filter(TableTrade.action == Action.SELL, TableTrade.by_external.is_(False),
                 TableTrade.job_id == job_id).first()

        return res.sum_grid_fee_paid_for_quantities if res.sum_grid_fee_paid_for_quantities is not None else 0.0
