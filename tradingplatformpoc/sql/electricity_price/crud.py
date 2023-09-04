import datetime
from contextlib import _GeneratorContextManager
from typing import Callable, Dict

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.electricity_price.models import ElectricityPrice as TableElectricityPrice


def db_to_electricity_price_dict(job_id: str, column: str,
                                 session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope
                                 ) -> Dict[datetime.datetime, float]:
    with session_generator() as db:
        elec_prices = db.execute(select(TableElectricityPrice.period.label('period'),
                                        getattr(TableElectricityPrice, column).label('price')
                                        ).where(TableElectricityPrice.job_id == job_id)).all()
        return {elec_price.period: elec_price.price for elec_price in elec_prices}
