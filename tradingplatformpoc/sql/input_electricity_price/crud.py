import logging
from contextlib import _GeneratorContextManager
from typing import Callable

import pandas as pd

from sqlalchemy import func

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.data.preprocessing import read_nordpool_data
from tradingplatformpoc.sql.input_data.models import InputData
from tradingplatformpoc.sql.input_electricity_price.models import InputElectricityPrice
from tradingplatformpoc.trading_platform_utils import weekdays_diff

logger = logging.getLogger(__name__)


def insert_input_electricity_price_to_db_if_empty(session_generator: Callable[[], _GeneratorContextManager[Session]]
                                                  = session_scope):
    with session_generator() as db:
        res = db.query(InputElectricityPrice).first()
        if res is None:
            logger.info('Populating input electricity price table.')
            electricity_price_df = read_nordpool_data()
            electricity_price_df = electricity_price_df.rename(columns={'datetime': 'period'})
            
            # Check that the nordpool data contains enough periods
            period_range = db.query(func.max(InputData.period).label('max'),
                                    func.min(InputData.period).label('min')).first()
            if (electricity_price_df.period.max() >= period_range.max) \
               & (electricity_price_df.period.min() <= period_range.min):

                electricity_price_dict = electricity_price_df.to_dict(orient='records')
                db.bulk_insert_mappings(InputElectricityPrice, electricity_price_dict)
            else:
                logger.error('Nordpool data contains less periods than input data plus max of n hours back.')
                raise Exception('Nordpool data contains less periods than input data plus max of n hours back.')
        else:
            logger.info('Input data table already populated.')


def electricity_price_series_from_db(session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope
                                     ) -> pd.Series:
    with session_generator() as db:
        res = db.query(InputElectricityPrice).all()
        if res is not None:
            logger.info('Fetching electricity price data from database.')
            return pd.DataFrame.from_records([{
                'period': x.period,
                'electricity_price': x.dayahead_se3_el_price}
                for x in res]).set_index('period').squeeze()
        else:
            logger.error('Could not fetch electricity price data from database.')
            raise Exception('Could not fetch electricity price data from database.')


def get_nordpool_data(price_year: int, trading_periods: pd.DatetimeIndex) -> pd.Series:
    """
    Get Nordpool data for the year specified.
    Note that self.config_data and self.trading_periods must be set for this method to work.
    """
    all_nordpool_data = electricity_price_series_from_db()
    year_offset = price_year - 2019  # All other data is for 2019
    # Need to also calculate a day offset, so that weekdays match up.
    days_offset = weekdays_diff(2019, price_year)
    datetime_offset = pd.DateOffset(years=year_offset, days=days_offset)
    corresponding_nordpool_data = all_nordpool_data[trading_periods + datetime_offset]
    # Need to change the datetimes so that they match all the other data
    corresponding_nordpool_data.index = corresponding_nordpool_data.index - datetime_offset
    return corresponding_nordpool_data
