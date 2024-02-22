import logging
from contextlib import _GeneratorContextManager
from typing import Callable

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.data.preprocessing import read_and_process_input_data
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


def read_input_column_df_from_db(
        column: str,
        session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) -> pd.DataFrame:
    with session_generator() as db:
        res = db.execute(select(InputData.period.label('period'),
                                getattr(InputData, column).label('value'))).all()
        if res is not None:
            return pd.DataFrame.from_records([{
                'period': x.period,
                column: x.value}
                for x in res])
        else:
            raise Exception('Could not fetch input data from database.')


def read_inputs_df_for_mock_data_generation(
        session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        res = db.execute(select(InputData.period.label('period'),
                                InputData.irradiation.label('irradiation'),
                                InputData.temperature.label('temperature'),
                                InputData.rad_energy.label('rad_energy'),
                                InputData.hw_energy.label('hw_energy'))).all()
        if res is not None:
            return pd.DataFrame.from_records([{
                'datetime': x.period,
                'irradiation': x.irradiation,
                'temperature': x.temperature,
                'rad_energy': x.rad_energy,
                'hw_energy': x.hw_energy}
                for x in res])
        else:
            raise Exception('Could not fetch input data from database.')
        

def read_inputs_df_for_agent_creation(
        session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        res = db.execute(select(InputData.period.label('period'),
                                InputData.irradiation.label('irradiation'),
                                InputData.coop_electricity_consumed.label('coop_electricity_consumed'),
                                InputData.coop_hot_tap_water_consumed.label('coop_hot_tap_water_consumed'),
                                InputData.coop_space_heating_consumed.label('coop_space_heating_consumed'),
                                InputData.coop_space_heating_produced.label('coop_space_heating_produced'))).all()
        if res is not None:
            return pd.DataFrame.from_records([{
                'period': x.period,
                'irradiation': x.irradiation,
                'coop_electricity_consumed': x.coop_electricity_consumed,
                'coop_hot_tap_water_consumed': x.coop_hot_tap_water_consumed,
                'coop_space_heating_consumed': x.coop_space_heating_consumed,
                'coop_space_heating_produced': x.coop_space_heating_produced}
                for x in res]).set_index('period')
        else:
            raise Exception('Could not fetch input data from database.')


def get_periods_from_db(session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope
                        ) -> pd.DatetimeIndex:
    with session_generator() as db:
        periods = db.execute(select(InputData.period)).all()
        if periods is not None:
            logger.info('Fetching periods from database.')
            return pd.DatetimeIndex([period for (period,) in periods]).sort_values()
        else:
            logger.error('Could not fetch periods from database.')
            raise Exception('Could not fetch periods from database.')
