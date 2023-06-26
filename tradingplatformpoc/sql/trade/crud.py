import datetime
from contextlib import _GeneratorContextManager
from typing import Callable, Collection, Dict

import pandas as pd

from sqlalchemy import func, select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.database import bulk_insert
from tradingplatformpoc.market.trade import Trade
from tradingplatformpoc.sql.trade.models import Trade as TableTrade


def heat_trades_from_db_for_periods(tradig_periods, job_id: str,
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
                                             & (TableTrade.period >= tradig_periods.min())
                                             & (TableTrade.period < tradig_periods.max())
                                             & (TableTrade.resource == 'HEATING'))).all()

        return {period: [trade for trade in trades_for_month if trade.period == period] for period in tradig_periods}


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


def aggregated_trades_by_agent(source: str, job_id: str,
                               session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    '''Fetches aggregated trades data from database for specified agent (source).'''
    with session_generator() as db:
        res = db.query(
            TableTrade.resource.label('resource'),
            TableTrade.action.label('action'),
            func.sum(TableTrade.quantity_pre_loss).label('sum_quantity_pre_loss'),
            func.sum(TableTrade.quantity_post_loss).label('sum_quantity_post_loss'),
            func.sum(TableTrade.total_bought_for).label('sum_total_bought_for'),
            func.sum(TableTrade.total_sold_for).label('sum_total_sold_for'),
            func.sum(TableTrade.tax_paid_for_quantity).label('sum_tax_paid_for_quantities'),
            func.sum(TableTrade.grid_fee_paid_for_quantity).label('grid_fee_paid_for_quantity')
        ).filter(TableTrade.source == source, TableTrade.job_id == job_id)\
         .group_by(TableTrade.resource, TableTrade.action).all()

        return res
