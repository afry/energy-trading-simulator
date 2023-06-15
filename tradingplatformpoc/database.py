from sqlmodel import SQLModel

from tradingplatformpoc.connection import db_engine


def create_db_and_tables():
    # SQLModel.metadata.drop_all(db_engine)
    SQLModel.metadata.create_all(db_engine)
