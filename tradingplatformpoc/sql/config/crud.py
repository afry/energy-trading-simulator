import logging
from contextlib import _GeneratorContextManager
from typing import Callable

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session, exists

from tradingplatformpoc.config.screen_config import agent_diff, param_diff
from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.config.models import Config, ConfigCreate
from tradingplatformpoc.sql.job.models import Job

logger = logging.getLogger(__name__)


def create_config_if_not_in_db(config: dict, config_id: str, description: str,
                               session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        # Check if matching config exists already
        exists = check_if_config_in_db(config=config, db=db)
        if not exists:
            db_config = create_config(ConfigCreate(id=config_id,
                                                   description=description,
                                                   agents=config['Agents'],
                                                   area_info=config['AreaInfo'],
                                                   mock_data_constants=config['MockDataConstants']),
                                      db=db)
            return db_config
        else:
            logger.warning('Configuration already exists in database with ID {}'.format(exists.id))
            return None


def create_config(config: ConfigCreate, db: Session):
    config_to_db = Config.from_orm(config)
    db.add(config_to_db)
    db.commit()
    db.refresh(config_to_db)
    return config_to_db


def check_if_config_in_db(config: dict, db: Session):
    configs_in_db = db.execute(select(Config)).all()
    for (config_in_db,) in configs_in_db:
        changed_area_info_params, changed_mock_data_params = \
            param_diff({'AreaInfo': config_in_db.area_info,
                        'MockDataConstants': config_in_db.mock_data_constants},
                       {'AreaInfo': config['AreaInfo'],
                        'MockDataConstants': config['MockDataConstants']})
        if (len(changed_area_info_params) == 0) and (len(changed_mock_data_params) == 0):
            agents_only_in_config_in_db, agents_only_in_new, diff_in_params = \
                agent_diff({'Agents': config_in_db.agents}, {'Agents': config['Agents']})
            if (len(agents_only_in_config_in_db) == 0) and (len(agents_only_in_new)
                                                            == 0) and (len(diff_in_params.keys()) == 0):
                return config_in_db
    return None


def read_config(config_id: str,
                session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    # TODO: Handle config not found
    with session_generator() as db:
        config = db.get(Config, config_id)
        if config is not None:
            return {'Agents': config.agents, 'AreaInfo': config.area_info,
                    'MockDataConstants': config.mock_data_constants}
        else:
            logger.error('Configuration with ID {} not found.'.format(config_id))
            return None


def get_all_config_ids_in_db_without_jobs(session_generator: Callable[[], _GeneratorContextManager[Session]]
                                          = session_scope):
    with session_generator() as db:
        res = db.query(Config.id).filter(~exists().where(Job.config_id == Config.id))
        return [config_id for (config_id,) in res]
    

def get_all_config_ids_in_db_with_jobs(session_generator: Callable[[], _GeneratorContextManager[Session]]
                                       = session_scope):
    with session_generator() as db:
        res = db.execute(select(Job, Config.description).join(Config, Job.config_id == Config.id)).all()
        return pd.DataFrame.from_records([{'Name': job.config_id, 'Description': desc,
                                           'Start time': job.init_time} for (job, desc) in res])
