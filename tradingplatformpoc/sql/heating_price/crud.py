from contextlib import _GeneratorContextManager
from typing import Callable, Dict, Tuple

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.heating_price.models import HeatingPrice as TableHeatingPrice


def db_to_heating_price_df(job_id: str,
                           session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope
                           ) -> pd.DataFrame:
    with session_generator() as db:
        heating_prices = db.execute(select(TableHeatingPrice).where(TableHeatingPrice.job_id == job_id)).all()
        return pd.DataFrame.from_records([{'year': heating_price.year,
                                           'month': heating_price.month,
                                           'estimated_retail_price': heating_price.estimated_retail_price,
                                           'estimated_wholesale_price': heating_price.estimated_wholesale_price,
                                           'exact_retail_price': heating_price.exact_retail_price,
                                           'exact_wholesale_price': heating_price.exact_wholesale_price
                                           } for (heating_price, ) in heating_prices])


def db_to_heating_price_dict(job_id: str, column: str,
                             session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope
                             ) -> Dict[Tuple[float, float], float]:
    with session_generator() as db:
        heating_prices = db.execute(select(TableHeatingPrice.year.label('year'),
                                           TableHeatingPrice.month.label('month'),
                                           getattr(TableHeatingPrice, column).label('price')
                                           ).where(TableHeatingPrice.job_id == job_id)).all()
        return {(heating_price.year, heating_price.month): heating_price.price
                for heating_price in heating_prices}
