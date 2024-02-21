import logging
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.config.models import Config
from tradingplatformpoc.sql.job.models import Job
from tradingplatformpoc.sql.results.models import PreCalculatedResults

logger = logging.getLogger(__name__)


def save_results(results: PreCalculatedResults,
                 session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        exists = get_results_for_job(results.job_id, raise_exception_if_not_found=False)
        if not exists:
            logger.info('Saving results for job ID ' + results.job_id)
            save_results_given_session(results, db)
        else:
            logger.info('Overwriting results for job ID ' + results.job_id)
            delete_results(results.job_id, db)
            save_results_given_session(results, db)


def save_results_given_session(results_to_db: PreCalculatedResults, db: Session):
    db.add(results_to_db)
    db.commit()
    db.refresh(results_to_db)


def delete_results(job_id: str,
                   session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        results = db.get(PreCalculatedResults, job_id)
        if not results:
            logger.error('No results in database for job ID ' + job_id)
        else:
            db.delete(results)
            db.commit()


def get_results_for_job(job_id: str, raise_exception_if_not_found: bool = False,
                        session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) \
        -> Optional[Dict[str, Any]]:
    """
    Fetches a dict of pre-calculated results for a given job ID.
    The keys in this dict are strings, as specified in ResultsKey. The values are of differing types, some floats, some
    more complex.
    If no results are found for the given job ID, this function will either return None, or raise an Exception, based
    on the raise_exception_if_not_found parameter.
    """
    with session_generator() as db:
        res = db.query(PreCalculatedResults.result_dict).filter(PreCalculatedResults.job_id == job_id).first()
        if res is not None:
            return res[0]
        else:
            if raise_exception_if_not_found:
                raise Exception('Found no results for job ID ' + job_id)
        return None


def get_all_results(session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) \
        -> List[Dict[str, Any]]:
    """
    Fetches all pre-calculated results in the database. Joins these with Config, via the Job table, to get the ID and
    description of the configuration which yielded the respective results.
    @return A list of dicts, each dict containing config ID, description, and the PreCalculatedResults.result_dict.
    """
    with session_generator() as db:
        res = db.execute(select(Config.id, Config.description, PreCalculatedResults.result_dict).
                         join(Job, Config.id == Job.config_id).
                         join(PreCalculatedResults, Job.id == PreCalculatedResults.job_id)).all()
        if res is not None:
            return [{'Config ID': config_id, 'Description': desc} | pre_calc_res_dict
                    for (config_id, desc, pre_calc_res_dict) in res]
        else:
            raise Exception('No results found!')
