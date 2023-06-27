import datetime
import logging
from contextlib import _GeneratorContextManager
from typing import Callable

import pytz

from sqlalchemy import insert, select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.job.models import Job

logger = logging.getLogger(__name__)


def get_all_job_ids_in_db(session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    pass
    # with session_generator() as db:
    #     db.session.query(
    #         Job.id
    #     ).distinct().all()


def create_job(job_id: str,
               session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        exists = db.execute(select(Job.id).where(Job.id == job_id)).first()
        if not exists:
            db.execute(insert(Job).values(id=job_id, init_time=datetime.datetime.now(pytz.utc)))
            db.commit()
            logger.info('Job created with ID {}.'.format(job_id))
        else:
            logger.warning('Job ID {} invalid, already in database.'.format(job_id))
            return False
        exists = db.execute(select(Job.id).where(Job.id == job_id)).first()
        return exists


def delete_job(job_id: str,
               session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        job = db.get(Job, job_id)
        if not job:
            logger.error('No job in database with ID {}'.format(job_id))

        # TODO: Delete job AND ALL RELATED DATA if run not completed
        
        db.delete(job)
        db.commit()
