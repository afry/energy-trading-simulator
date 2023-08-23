import datetime
import itertools
import operator
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List, Tuple

import pandas as pd

from sqlalchemy import func, select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.market.bid import Action
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


def trades_to_db_dict(bids_list: List[Trade], job_id: str) -> List[Dict[str, Any]]:
    dict = [{'job_id': job_id,
             'period': x.period,
             'source': x.source,
             'by_external': x.by_external,
             'action': x.action,
             'resource': x.resource,
             'quantity_pre_loss': x.quantity_pre_loss,
             'quantity_post_loss': x.quantity_post_loss,
             'price': x.price,
             'market': x.market,
             'tax_paid': x.tax_paid,
             'grid_fee_paid': x.grid_fee_paid}
            for some_collection in bids_list for x in some_collection]
    return dict


def db_to_aggregated_trades_by_agent(job_id: str,
                                     session_generator: Callable[[], _GeneratorContextManager[Session]]
                                     = session_scope):
    '''Fetches aggregated trades data from database for specified agent (source).'''
    with session_generator() as db:
        res = db.query(
            TableTrade.source.label('source'),
            TableTrade.resource.label('resource'),
            TableTrade.action.label('action'),
            func.sum(TableTrade.quantity_pre_loss).label('sum_quantity_pre_loss'),
            func.sum(TableTrade.quantity_post_loss).label('sum_quantity_post_loss'),
            func.sum(TableTrade.total_bought_for).label('sum_total_bought_for'),
            func.sum(TableTrade.total_sold_for).label('sum_total_sold_for'),
            func.sum(TableTrade.tax_paid_for_quantity).label('sum_tax_paid_for_quantities'),
            func.sum(TableTrade.grid_fee_paid_for_quantity).label('grid_fee_paid_for_quantity')
        ).filter(TableTrade.job_id == job_id)\
         .group_by(TableTrade.source, TableTrade.resource, TableTrade.action).all()

        return dict((source, list(vals)) for source, vals in
                    itertools.groupby(res, operator.itemgetter(0)))


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
