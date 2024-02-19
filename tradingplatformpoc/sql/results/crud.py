import logging
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, Optional

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.results.models import PreCalculatedResults

logger = logging.getLogger(__name__)


def save_results(results: PreCalculatedResults,
                 session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        exists = get_results(results.job_id, raise_exception_if_not_found=False)
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


def get_results(job_id: str, raise_exception_if_not_found: bool = False,
                session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) \
        -> Optional[Dict[str, Any]]:
    with session_generator() as db:
        return get_results_given_session(job_id, db, raise_exception_if_not_found)


def get_results_given_session(job_id: str, db: Session, raise_exception_if_not_found: bool = False) \
        -> Optional[Dict[str, Any]]:
    res = db.query(PreCalculatedResults.result_dict).filter(PreCalculatedResults.job_id == job_id).first()
    if res is not None:
        return res[0]
    else:
        if raise_exception_if_not_found:
            raise Exception('Found no results for job ID ' + job_id)
    return None
