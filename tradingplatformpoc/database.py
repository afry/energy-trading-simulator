import logging
from contextlib import _GeneratorContextManager
from typing import Callable, List

from sqlalchemy import text
from sqlalchemy_batch_inserts import enable_batch_inserting

from sqlmodel import SQLModel, Session

from tradingplatformpoc.app.app_constants import DEFAULT_CONFIG_NAME
from tradingplatformpoc.config.access_config import read_config
from tradingplatformpoc.connection import db_engine, session_scope
from tradingplatformpoc.sql.config.crud import create_config_if_not_in_db


logger = logging.getLogger(__name__)


def create_db_and_tables():
    SQLModel.metadata.create_all(db_engine)
    logger.info('Creating db and tables')

    # Grant privileges to afryx_admin - there is probably a better way to do this
    with db_engine.connect() as connection:
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE agent TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE config TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE electricity_price TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE extra_cost TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE heating_price TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE input_data TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE input_electricity_price TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE job TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE level TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE mock_data TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE results TO afryx_admin"))
        connection.execute(text("GRANT ALL PRIVILEGES ON TABLE trade TO afryx_admin"))
        connection.commit()


def drop_db_and_tables():
    SQLModel.metadata.drop_all(db_engine)
    logger.info('Dropping db and tables')


def bulk_insert(table_type, dicts: List[dict],
                session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        enable_batch_inserting(db)
        db.bulk_insert_mappings(table_type, dicts)
        db.commit()


def insert_default_config_into_db():
    config = read_config()

    create_config_if_not_in_db(config, DEFAULT_CONFIG_NAME, 'Default setup')
