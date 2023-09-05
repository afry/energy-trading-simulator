import logging
from contextlib import _GeneratorContextManager
from typing import Callable

import pandas as pd

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.data.preproccessing import clean, read_nordpool_data
from tradingplatformpoc.sql.input_electricity_price.models import InputElectricityPrice


logger = logging.getLogger(__name__)


def insert_input_electricity_price_to_db_if_empty(session_generator: Callable[[], _GeneratorContextManager[Session]]
                                                  = session_scope):
    with session_generator() as db:
        res = db.query(InputElectricityPrice).first()
        if res is None:
            logger.info('Populating input electricity price table.')
            electricity_price_series = read_nordpool_data()
            electricity_price_df = pd.DataFrame(electricity_price_series).reset_index()
            electricity_price_df = clean(electricity_price_df).reset_index()
            electricity_price_df = electricity_price_df.rename(
                columns={'datetime': 'period', 'dayahead_SE3_el_price': 'dayahead_se3_el_price'})
            electricity_price_dict = electricity_price_df.to_dict(orient='records')
            db.bulk_insert_mappings(InputElectricityPrice, electricity_price_dict)
        else:
            logger.info('Input data table already populated.')
