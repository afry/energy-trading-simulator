
import datetime
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.sql.clearing_price.models import ClearingPrice as TableClearingPrice


def clearing_prices_to_db_dict(clearing_prices_dict: Dict[datetime.datetime, Dict[Resource, float]],
                               job_id: str) -> List[Dict[str, Any]]:
    return [{'period': period,
             'job_id': job_id,
             'resource': resource,
             'price': price}
            for period, some_dict in clearing_prices_dict.items()
            for resource, price in some_dict.items()]


def get_periods_from_clearing_prices(
        job_id: str, session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope
) -> List[datetime.datetime]:
    with session_generator() as db:
        periods = db.execute(select(TableClearingPrice.period).where(TableClearingPrice.job_id == job_id)).all()
        return [period for (period,) in periods]


def db_to_construct_local_prices_df(job_id: str, session_generator: Callable[[], _GeneratorContextManager[Session]]
                                    = session_scope) -> pd.DataFrame:
    """
    Constructs a pandas DataFrame on the format which fits Altair, which we use for plots.
    """
    with session_generator() as db:
        clearing_prices = db.query(TableClearingPrice).filter(TableClearingPrice.job_id == job_id).all()

        if len(clearing_prices) > 0:
            clearing_prices_df = pd.DataFrame.from_records([{
                'period': price.period,
                'Resource': price.resource,
                'value': price.price,
            } for price in clearing_prices])
            clearing_prices_df['variable'] = app_constants.LOCAL_PRICE_STR
            return clearing_prices_df
        else:
            return pd.DataFrame()
