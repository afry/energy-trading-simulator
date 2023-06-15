import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv

import sqlalchemy.orm as sa_orm

from sqlmodel import Session, create_engine

dotenv_path = Path('.env')
load_dotenv(dotenv_path=dotenv_path)

DB_URI = f"postgresql+psycopg2://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}@{os.getenv('PG_HOST')}/{os.getenv('PG_DATABASE')}"  # noqa: E501

db_engine = create_engine(
    DB_URI,
    echo=False,
    pool_pre_ping=True
)

SessionMaker = sa_orm.sessionmaker(bind=db_engine, class_=Session)

logger = logging.getLogger(__name__)


def get_session():
    with Session(db_engine) as session:
        yield session


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
