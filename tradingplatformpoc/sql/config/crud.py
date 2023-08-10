import logging
from collections import Counter
from contextlib import _GeneratorContextManager
from typing import Callable, Dict, List

import pandas as pd

from sqlalchemy import select

from sqlmodel import Session, exists

from tradingplatformpoc.config.screen_config import param_diff
from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.agent.crud import create_agent_if_not_in_db
from tradingplatformpoc.sql.agent.models import Agent as TableAgent
from tradingplatformpoc.sql.config.models import Config, ConfigCreate
from tradingplatformpoc.sql.job.models import Job

logger = logging.getLogger(__name__)


def create_config_if_not_in_db(config: dict, config_id: str, description: str,
                               session_generator: Callable[[], _GeneratorContextManager[Session]]
                               = session_scope) -> dict:
    # TODO validate ID
    id_exists = check_if_id_in_db(config_id=config_id)
    if id_exists is not None:
        logger.warning('Configuration ID {} already exists in database.'.format(id_exists))
        return {'created': False, 'id': id_exists,
                'message': 'Configuration ID {} already exists in database.'.format(id_exists)}

    agent_name_and_ids = {agent['Name']: create_agent_if_not_in_db(agent) for agent in config['Agents'][:]}

    # Check if matching config exists already
    config_exists_id = check_if_config_in_db(config=config, agent_ids=agent_name_and_ids.values())
    if config_exists_id is None:
        db_config_id = create_config(ConfigCreate(id=config_id,
                                                  description=description,
                                                  agents_spec=agent_name_and_ids,
                                                  area_info=config['AreaInfo'],
                                                  mock_data_constants=config['MockDataConstants']))
        logger.info('Configuration with ID {} created!'.format(db_config_id))
        return {'created': True, 'id': db_config_id, 'message': 'Config created with ID {}'.format(db_config_id)}
    else:
        logger.warning('Configuration already exists in database with ID {}'.format(config_exists_id))
        return {'created': False, 'id': config_exists_id,
                'message': 'Configuration already exists in database with ID {}'.format(config_exists_id)}


def create_config(config: ConfigCreate,
                  session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        config_to_db = Config.from_orm(config)
        db.add(config_to_db)
        db.commit()
        db.refresh(config_to_db)
        return config_to_db.id


def check_if_config_in_db(config: dict, agent_ids: List[str],
                          session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    with session_generator() as db:
        configs_in_db = db.execute(select(Config)).all()
        for (config_in_db,) in configs_in_db:
            changed_area_info_params, changed_mock_data_params = \
                param_diff({'AreaInfo': config_in_db.area_info,
                            'MockDataConstants': config_in_db.mock_data_constants},
                           {'AreaInfo': config['AreaInfo'],
                            'MockDataConstants': config['MockDataConstants']})
            if (len(changed_area_info_params) == 0) and (len(changed_mock_data_params) == 0):
                diff1 = Counter(config_in_db.agents_spec.values()) - Counter(agent_ids)
                diff2 = Counter(agent_ids) - Counter(config_in_db.agents_spec.values())

                if (len(diff1) == 0) & (len(diff2) == 0):
                    return config_in_db.id
        return None


def read_config(config_id: str,
                session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope):
    # TODO: Handle config not found
    with session_generator() as db:
        config = db.get(Config, config_id)
        if config is not None:
            res = db.execute(select(TableAgent).where(TableAgent.id.in_(config.agents_spec.values()))).all()
            agents = [{'Name': [name for name, aid in config.agents_spec.items() if aid == agent.id][0],
                       **agent.agent_config} for (agent,) in res]
            return {'Agents': agents, 'AreaInfo': config.area_info,
                    'MockDataConstants': config.mock_data_constants}
        else:
            logger.error('Configuration with ID {} not found.'.format(config_id))
            return None


def get_all_config_ids_in_db_without_jobs(session_generator: Callable[[], _GeneratorContextManager[Session]]
                                          = session_scope):
    with session_generator() as db:
        res = db.query(Config.id).filter(~exists().where(Job.config_id == Config.id))
        return [config_id for (config_id,) in res]
    

def get_all_job_config_id_pairs_in_db(session_generator: Callable[[], _GeneratorContextManager[Session]]
                                      = session_scope) -> Dict[str, str]:
    with session_generator() as db:
        res = db.execute(select(Config.id.label('config_id'), Job.id.label('job_id'))
                         .join(Config, Job.config_id == Config.id)).all()
        return {elem.config_id: elem.job_id for elem in res}


def get_all_config_ids_in_db_with_jobs_df(session_generator: Callable[[], _GeneratorContextManager[Session]]
                                          = session_scope):
    with session_generator() as db:
        res = db.execute(select(Job, Config.description).join(Config, Job.config_id == Config.id)).all()
        return pd.DataFrame.from_records([{'Job ID': job.id, 'Config ID': job.config_id, 'Description': desc,
                                           'Start time': job.init_time, 'End time': job.end_time}
                                         for (job, desc) in res])


def get_all_config_ids_in_db(session_generator: Callable[[], _GeneratorContextManager[Session]]
                             = session_scope):
    with session_generator() as db:
        res = db.execute(select(Config.id).outerjoin(Job, Job.config_id == Config.id)).all()
        return [config_id for (config_id,) in res]


def get_all_configs_in_db(session_generator: Callable[[], _GeneratorContextManager[Session]]
                          = session_scope):
    with session_generator() as db:
        res = db.execute(select(Config, Job.init_time).outerjoin(Job, Job.config_id == Config.id)).all()
        return pd.DataFrame.from_records([{'Config ID': config.id, 'Description': config.description,
                                           'Start time': init_time} for (config, init_time) in res])


def check_if_id_in_db(config_id: str,
                      session_generator: Callable[[], _GeneratorContextManager[Session]]
                      = session_scope):
    with session_generator() as db:
        res = db.execute(select(Config.id).where(Config.id == config_id)).first()
        return res[0] if res is not None else None
