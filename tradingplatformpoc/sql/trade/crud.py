import datetime
import itertools
import operator
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List, Optional

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
    

def electr_trades_for_periods_to_df(job_id: str, resource: Resource, action: Action, trading_periods,
                                    session_generator: Callable[[], _GeneratorContextManager[Session]]
                                    = session_scope) -> pd.DataFrame:
    """Get the summed amount of electricity used each period for all agents combined.
    """
    with session_generator() as db:
        trades = db.execute(select(TableTrade.period,
                            func.sum(TableTrade.quantity_pre_loss).label("total_quantity"),
                            func.to_char(TableTrade.period, 'D').label("weekday"))
                            .where(TableTrade.job_id == job_id,
                                   TableTrade.resource == resource,
                                   TableTrade.action == action,
                                   TableTrade.period.in_(trading_periods))
                            .group_by(TableTrade.period)
                            .order_by(TableTrade.period)).all()
        return pd.DataFrame.from_records([{'period': trade.period,
                                           'total_quantity': trade.total_quantity,
                                           'weekday': trade.weekday
                                           } for trade in trades])


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


def db_to_aggregated_trade_df(job_id: str, resource: Resource, action: Action,
                              session_generator: Callable[[], _GeneratorContextManager[Session]]
                              = session_scope):
    """Fetches aggregated trades data from database for specified agent (source), resource and action."""
    with session_generator() as db:
        if action == Action.BUY:
            label = "bought"
            quantity_attribute = "quantity_pre_loss"
            action_attribute = "bought_for"
        elif action == Action.SELL:
            label = "sold"
            quantity_attribute = "quantity_post_loss"
            action_attribute = "sold_for"
        res = db.query(
            TableTrade.source.label('Agent'),
            func.sum(getattr(TableTrade, quantity_attribute)).label('Total quantity ' + label + ' [kWh]'),
            func.sum(getattr(TableTrade, action_attribute)).label('Total amount ' + label + ' for [SEK]'),
        ).filter(TableTrade.job_id == job_id,
                 TableTrade.action == action,
                 TableTrade.resource == resource)\
         .group_by(TableTrade.source, TableTrade.resource).all()

        df = pd.DataFrame(res).set_index('Agent')
        df['Average ' + action.name.lower() + ' price [SEK/kWh]'] = \
            df['Total amount ' + label + ' for [SEK]'] / df['Total quantity ' + label + ' [kWh]']
        return df
    

def get_total_traded_for_agent(job_id: str, agent_guid: str, action: Action,
                               session_generator: Callable[[], _GeneratorContextManager[Session]]
                               = session_scope):
    with session_generator() as db:
        if action == Action.BUY:
            action_attribute = "bought_for"
        elif action == Action.SELL:
            action_attribute = "sold_for"
        res = db.query(
            func.sum(getattr(TableTrade, action_attribute)),
        ).filter(TableTrade.job_id == job_id,
                 TableTrade.source == agent_guid,
                 TableTrade.action == action).first()
        return res[0] if res[0] is not None else 0.0


def db_to_trades_by_agent_and_resource_action(job_id: str, agent_guid: str, resource: Resource, action: Action,
                                              session_generator: Callable[[], _GeneratorContextManager[Session]]
                                              = session_scope):
    with session_generator() as db:
        if action == Action.BUY:
            attribute = 'quantity_pre_loss'
        elif action == Action.SELL:
            attribute = 'quantity_post_loss'
        return db.query(
            TableTrade.period.label('period'),
            getattr(TableTrade, attribute).label(attribute),
            TableTrade.price.label('price'),
            TableTrade.month.label('month'),
            TableTrade.year.label('year'),
        ).filter(
            TableTrade.job_id == job_id,
            TableTrade.source == agent_guid,
            TableTrade.action == action,
            TableTrade.resource == resource).all()
    

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


def get_total_tax_paid(job_id: str, agent_guid: Optional[str] = None,
                       session_generator: Callable[[], _GeneratorContextManager[Session]]
                       = session_scope) -> float:
    with session_generator() as db:
        query = db.query(
            func.sum(TableTrade.tax_paid_for_quantity).label('sum_tax_paid_for_quantities'),
        ).filter(TableTrade.action == Action.SELL,
                 TableTrade.job_id == job_id)
        if agent_guid is not None:
            query = query.filter(TableTrade.source == agent_guid)
        res = query.first()

        return res.sum_tax_paid_for_quantities if res.sum_tax_paid_for_quantities is not None else 0.0


def get_total_grid_fee_paid_on_internal_trades(job_id: str, agent_guid: Optional[str] = None,
                                               session_generator: Callable[[], _GeneratorContextManager[Session]]
                                               = session_scope) -> float:
    with session_generator() as db:
        query = db.query(
            func.sum(TableTrade.grid_fee_paid_for_quantity).label('sum_grid_fee_paid_for_quantities'),
        ).filter(TableTrade.action == Action.SELL, TableTrade.by_external.is_(False),
                 TableTrade.job_id == job_id)
        if agent_guid is not None:
            query = query.filter(TableTrade.source == agent_guid)
        res = query.first()

        return res.sum_grid_fee_paid_for_quantities if res.sum_grid_fee_paid_for_quantities is not None else 0.0


def get_total_import_export(job_id: str, resource: Resource, action: Action,
                            periods: Optional[List[datetime.datetime]] = None,
                            session_generator: Callable[[], _GeneratorContextManager[Session]]
                            = session_scope) -> float:
    with session_generator() as db:
        query = db.query(
            func.sum(TableTrade.quantity_post_loss).label('sum_quantity_post_loss'),
        ).filter(TableTrade.job_id == job_id,
                 TableTrade.by_external,
                 TableTrade.resource == resource,
                 TableTrade.action == action)
        if periods is not None:
            query = query.filter(TableTrade.period.in_(periods))
        res = query.first()
        return res.sum_quantity_post_loss if res.sum_quantity_post_loss is not None else 0.0


def get_import_export_df(job_ids: List[str],
                         session_generator: Callable[[], _GeneratorContextManager[Session]]
                         = session_scope) -> float:
    with session_generator() as db:
        res = db.query(
            TableTrade.job_id.label('job_id'),
            TableTrade.period.label('period'),
            TableTrade.resource.label('resource'),
            TableTrade.action.label('action'),
            TableTrade.quantity_post_loss.label('quantity_post_loss'),
        ).filter(TableTrade.job_id.in_(job_ids),
                 TableTrade.by_external).all()
        if len(res) > 0:
            return pd.DataFrame.from_records([{'job_id': elem.job_id,
                                               'period': elem.period,
                                               'action': elem.action,
                                               'resource': elem.resource,
                                               'quantity_post_loss': elem.quantity_post_loss}
                                              for elem in res])
        else:
            return pd.DataFrame(columns=['job_id', 'period', 'action', 'resource', 'quantity_post_loss'])
