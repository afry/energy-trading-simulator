import logging
from contextlib import _GeneratorContextManager
from typing import Callable

from sqlmodel import SQLModel, Session

from tradingplatformpoc.app.app_constants import DEFAULT_CONFIG_NAME
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


def bulk_insert(objects: list,
                session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        db.bulk_save_objects(objects)
        db.commit()


def insert_default_config_into_db():
    config = read_config()

    create_config_if_not_in_db(config, DEFAULT_CONFIG_NAME, 'Default setup')
