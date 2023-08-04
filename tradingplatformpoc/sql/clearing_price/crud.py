
import datetime
from contextlib import _GeneratorContextManager
from typing import Callable, Dict, List

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.sql.clearing_price.models import ClearingPrice as TableClearingPrice


def clearing_prices_to_db_objects(clearing_prices_dict:
                                  Dict[datetime.datetime, Dict[Resource, float]], job_id: str
                                  ) -> List[TableClearingPrice]:
    objects = [TableClearingPrice(period=period,
                                  job_id=job_id,
                                  resource=resource,
                                  price=price)
               for period, some_dict in clearing_prices_dict.items()
               for resource, price in some_dict.items()]
    return objects


def get_periods_from_clearing_prices(
        job_id: str, session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope
) -> List[datetime.datetime]:
    with session_generator() as db:
        periods = db.execute(select(TableClearingPrice.period).where(TableClearingPrice.job_id == job_id)).all()
        return [period for (period,) in periods]
