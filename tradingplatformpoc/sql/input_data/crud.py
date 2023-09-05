import logging
from contextlib import _GeneratorContextManager
from typing import Callable

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.data.preproccessing import read_and_process_input_data
from tradingplatformpoc.sql.input_data.models import InputData


logger = logging.getLogger(__name__)


def insert_input_data_to_db_if_empty(session_generator: Callable[[], _GeneratorContextManager[Session]]
                                     = session_scope):
    with session_generator() as db:
        res = db.query(InputData).first()
        if res is None:
            logger.info('Populating input data table.')
            input_df = read_and_process_input_data()
            input_df = input_df.rename(columns={'datetime': 'period'})
            input_dict = input_df.to_dict(orient='records')
            db.bulk_insert_mappings(InputData, input_dict)
        else:
            logger.info('Input data table already populated.')


def read_temperature_df_from_db(
        session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) -> pd.DataFrame:
    with session_generator() as db:
        res = db.execute(select(InputData.period.label('period'),
                                InputData.temperature.label('temperature'))).all()
        if res is not None:
            return pd.DataFrame.from_records([{
                'period': x.period,
                'temperature': x.temperature}
                for x in res])
        else:
            raise Exception('Could not fetch input data from database.')


def read_inputs_df_for_mock_data_generation(
        session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        res = db.execute(select(InputData)).all()
        if res is not None:
            return pd.DataFrame.from_records([{
                'datetime': x.period,
                'irradiation': x.irradiation,
                'temperature': x.temperature,
                'rad_energy': x.rad_energy,
                'hw_energy': x.hw_energy}
                for (x,) in res])
        else:
            raise Exception('Could not fetch input data from database.')
