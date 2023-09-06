import datetime
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List

import pandas as pd

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.level.models import Level


def levels_to_db_dict(levels_dict: Dict[str, Dict[datetime.datetime, float]],
                      level_type: str, job_id: str) -> List[Dict[str, Any]]:
    dict = ({'period': period,
             'job_id': job_id,
             'agent': agent,
             'type': level_type,
             'level': level}
            for agent, some_dict in levels_dict.items()
            for period, level in some_dict.items())
    return dict


def db_to_viewable_level_df_by_agent(job_id: str, agent_guid: str, level_type: str,
                                     session_generator: Callable[[], _GeneratorContextManager[Session]]
                                     = session_scope):
    """
    Fetches trades data from database for specified agent (agent_guid) and changes to a df.
    """
    with session_generator() as db:
        levels = db.query(Level).filter(Level.agent == agent_guid,
                                        Level.job_id == job_id,
                                        Level.type == level_type).all()

        if len(levels) > 0:
            return pd.DataFrame.from_records([{'period': level.period,
                                               'level': level.level
                                               } for level in levels], index='period')
        else:
            return pd.DataFrame(columns=['period', 'type', 'level'])
