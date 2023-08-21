from contextlib import _GeneratorContextManager
from typing import Any, Callable, Collection, Dict, List

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.heating_price.models import HeatingPrice as TableHeatingPrice


def external_heating_prices_to_db_objects(
        heating_price_by_ym_lst: List[Dict[str, Any]],
        job_id: str) -> Collection[TableHeatingPrice]:
    return [TableHeatingPrice(job_id=job_id, **args) for args in heating_price_by_ym_lst]


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


def db_to_heating_price_dicts(job_id: str,
                              session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope
                              ) -> pd.DataFrame:
    with session_generator() as db:
        heating_prices = db.execute(select(TableHeatingPrice).where(TableHeatingPrice.job_id == job_id)).all()
        exact_retail_heat_price_by_ym = \
            {(heating_price.year, heating_price.month): heating_price.exact_retail_price
             for (heating_price, ) in heating_prices}
        exact_wholesale_heat_price_by_ym = \
            {(heating_price.year, heating_price.month): heating_price.exact_wholesale_price
             for (heating_price, ) in heating_prices}
        return exact_retail_heat_price_by_ym, exact_wholesale_heat_price_by_ym
