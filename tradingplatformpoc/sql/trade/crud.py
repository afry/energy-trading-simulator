import datetime
from contextlib import _GeneratorContextManager
from typing import Callable, Dict

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
# from tradingplatformpoc.market.bid import Action
# from tradingplatformpoc.market.trade import Market
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
