import datetime
import logging
from contextlib import _GeneratorContextManager
from typing import Callable

import pytz

from sqlalchemy import delete, select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.bid.models import Bid as TableBid
from tradingplatformpoc.sql.clearing_price.models import ClearingPrice
from tradingplatformpoc.sql.electricity_price.models import ElectricityPrice as TableElectricityPrice
from tradingplatformpoc.sql.extra_cost.models import ExtraCost as TableExtraCost
from tradingplatformpoc.sql.heating_price.models import HeatingPrice as TableHeatingPrice
from tradingplatformpoc.sql.job.models import Job, JobCreate
from tradingplatformpoc.sql.level.models import Level
from tradingplatformpoc.sql.results.models import PreCalculatedResults
from tradingplatformpoc.sql.trade.models import Trade as TableTrade

logger = logging.getLogger(__name__)


def get_all_job_ids_in_db(session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    pass
    # with session_generator() as db:
    #     db.session.query(
    #         Job.id
    #     ).distinct().all()


def create_job(job: JobCreate, db: Session):
    job_to_db = Job.from_orm(job)
    db.add(job_to_db)
    db.commit()
    db.refresh(job_to_db)
    return job_to_db


def create_job_if_new_config(config_id: str,
                             session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        exists = get_job_id_for_config(config_id, db)
        if not exists:
            job_to_db = create_job(JobCreate(config_id=config_id), db=db)
            logger.info('Job created with ID {}.'.format(job_to_db.id))
            return job_to_db.id
        else:
            logger.warning('A job for configuration ID {} already in database.'.format(config_id))
            return None


def delete_job(job_id: str,
               session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        job = db.get(Job, job_id)
        if not job:
            logger.error('No job in database with ID {}'.format(job_id))
        else:
            logger.info('Deleting job in database with ID {}, along with all related data'.format(job_id))
            # Delete job AND ALL RELATED DATA
            db.execute(delete(TableBid).where(TableBid.job_id == job_id))
            db.execute(delete(ClearingPrice).where(ClearingPrice.job_id == job_id))
            db.execute(delete(TableElectricityPrice).where(TableElectricityPrice.job_id == job_id))
            db.execute(delete(TableExtraCost).where(TableExtraCost.job_id == job_id))
            db.execute(delete(TableHeatingPrice).where(TableHeatingPrice.job_id == job_id))
            db.execute(delete(Level).where(Level.job_id == job_id))
            db.execute(delete(TableTrade).where(TableTrade.job_id == job_id))
            db.execute(delete(PreCalculatedResults).where(PreCalculatedResults.job_id == job_id))

            db.delete(job)
            db.commit()
            logger.info('Job {} deleted'.format(job_id))


# TODO: If job for config exists show or delete and rerun
def get_job_id_for_config(config_id: str, db: Session):
    job_for_config = db.execute(select(Job.id).where(Job.config_id == config_id)).first()
    if job_for_config:
        return job_for_config.id
    else:
        return None


def update_job_with_time(job_id: str, time_attribute: str,
                         session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        job_to_update = db.get(Job, job_id)

        if not job_to_update:
            logger.error('No job to update in database with ID {}'.format(job_id))
            raise Exception("No job to update in database with ID {}'.format(job_id)")

        setattr(job_to_update, time_attribute, datetime.datetime.now(pytz.utc))

        db.add(job_to_update)
        db.commit()
        db.refresh(job_to_update)


def get_all_ongoing_jobs(session_generator: Callable[[], _GeneratorContextManager[Session]]
                         = session_scope):
    with session_generator() as db:
        res = db.query(Job.config_id).filter(Job.start_time.is_not(None), Job.end_time.is_(None)).all()
        return [config_id for (config_id,) in res]


def get_config_id_for_job_id(job_id: str,
                             session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        res = db.query(Job.config_id.label('config_id')).filter(Job.id == job_id).first()
        if res is not None:
            return res.config_id
        else:
            raise Exception('Found no config ID for job ID.')


def get_all_queued_jobs(session_generator: Callable[[], _GeneratorContextManager[Session]]
                        = session_scope):
    with session_generator() as db:
        res = db.query(Job.id).filter(Job.start_time.is_(None), Job.end_time.is_(None)).\
            order_by(Job.created_at.asc()).all()
        return [job_id for (job_id,) in res]
