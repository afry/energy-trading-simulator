import logging
from contextlib import _GeneratorContextManager
from typing import Callable
# from time import perf_counter

from sqlmodel import SQLModel, Session

from tradingplatformpoc.config.access_config import read_config
from tradingplatformpoc.connection import db_engine, session_scope
from tradingplatformpoc.sql.config.crud import create_config_if_not_in_db


logger = logging.getLogger(__name__)


def create_db_and_tables():
    SQLModel.metadata.create_all(db_engine)
    logger.info('Creating db and tables')


def drop_db_and_tables():
    SQLModel.metadata.drop_all(db_engine)
    logger.info('Dropping db and tables')


def bulk_insert(table_type, objects: list,
                session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        # start = perf_counter()
        db.bulk_insert_mappings(table_type, objects)
        db.commit()
        # elapsed_time = perf_counter() - start
        # logger.info(f'time loop finish {elapsed_time}')


def insert_default_config_into_db():
    config = read_config()

    create_config_if_not_in_db(config, 'default', 'Default setup')
