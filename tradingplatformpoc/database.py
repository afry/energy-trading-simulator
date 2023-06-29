from contextlib import _GeneratorContextManager
from typing import Callable

from sqlalchemy import delete

from sqlmodel import SQLModel, Session

from tradingplatformpoc.config.access_config import read_config
from tradingplatformpoc.connection import db_engine, session_scope
from tradingplatformpoc.sql.bid.models import Bid as TableBid
from tradingplatformpoc.sql.config.crud import create_config_if_not_in_db
from tradingplatformpoc.sql.extra_cost.models import ExtraCost as TableExtraCost
from tradingplatformpoc.sql.trade.models import Trade as TableTrade


def create_db_and_tables():
    # SQLModel.metadata.drop_all(db_engine)
    SQLModel.metadata.create_all(db_engine)


def bulk_insert(objects: list,
                session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        db.bulk_save_objects(objects)
        db.commit()


def delete_from_db(job_id: str, table_name: str,
                   session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        if table_name == 'Trade':
            db.execute(delete(TableTrade).where(TableTrade.job_id == job_id))
        elif table_name == 'Bid':
            db.execute(delete(TableBid).where(TableBid.job_id == job_id))
        elif table_name == 'ExtraCost':
            db.execute(delete(TableExtraCost).where(TableExtraCost.job_id == job_id))
        db.commit()


def insert_default_config_into_db():
    config = read_config(name='default')

    create_config_if_not_in_db(config, 'default', 'Default setup')
