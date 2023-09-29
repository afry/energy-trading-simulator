import logging
from contextlib import contextmanager
from typing import Generator

import sqlalchemy.orm as sa_orm

from sqlmodel import Session, create_engine

from tradingplatformpoc.settings import settings

logger = logging.getLogger(__name__)

DB_URI = f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}/{settings.DB_DATABASE}"  # noqa: E501


def create_db_engine(db_uri: str):
    return create_engine(
        db_uri,
        echo=False,
        pool_pre_ping=True,
        connect_args={'options': '-csearch_path={}'.format('simulation')}
    )


db_engine = create_db_engine(DB_URI)


SessionMaker = sa_orm.sessionmaker(class_=Session, bind=db_engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = SessionMaker()
    
    try:
        yield session
        session.commit()
    
    except Exception as e:
        logger.warning('Encountered exception in database session. Will rollback. Exception to follow...')
        logger.exception(e)
        session.rollback()
    
    finally:
        session.close()
