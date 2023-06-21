import datetime
from contextlib import _GeneratorContextManager
from typing import Callable, Collection, Dict

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market, Trade
from tradingplatformpoc.sql.trade.models import Trade as TableTrade


def heat_trades_from_db_for_periods(tradig_periods, job_id: str,
                                    session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope)\
        -> Dict[datetime.datetime, Collection[Trade]]:
    with session_generator() as db:
        # month_start = datetime.datetime(year, month, 1)
        # month_end = datetime.datetime(year, month, 1) + datetime.timedelta(months=1)
        trades_for_month = db.execute(select(TableTrade)
                                      .where((TableTrade.job_id == job_id)
                                             & (TableTrade.period >= tradig_periods.min())
                                             & (TableTrade.period < tradig_periods.max())
                                             & (TableTrade.resource == 'HEATING'))).all()

        # periods_in_month = pd.date_range(month_start, month_end, freq='1h', inclusive='left')

        return {period: [Trade(period=trade.period,
                               action=Action[trade.action],
                               resource=Resource[trade.resource],
                               quantity=trade.quantity_pre_loss,
                               loss=1 - (trade.quantity_post_loss / trade.quantity_pre_loss),
                               price=trade.price,
                               source=trade.source,
                               by_external=trade.by_external,
                               market=Market[trade.market],
                               tax_paid=trade.tax_paid,
                               grid_fee_paid=trade.grid_fee_paid)
                         for (trade, ) in trades_for_month if trade.period == period]
                for period in tradig_periods}
