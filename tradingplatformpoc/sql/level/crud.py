import datetime
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List

import pandas as pd

from sqlalchemy import func

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.market.trade import TradeMetadataKey
from tradingplatformpoc.sql.level.models import Level
from tradingplatformpoc.trading_platform_utils import flatten_collection

NOT_AN_AGENT = ''


def levels_to_db_dict(levels_dict: Dict[str, Dict[datetime.datetime, float]],
                      level_type: str, job_id: str) -> List[Dict[str, Any]]:
    return [{'period': period,
             'job_id': job_id,
             'agent': agent,
             'type': level_type,
             'level': level}
            for agent, some_dict in levels_dict.items()
            for period, level in some_dict.items()]


def tmk_levels_dict_to_db_dict(tmk_levels_dict: Dict[TradeMetadataKey, Dict[str, Dict[datetime.datetime, float]]],
                               job_id: str) -> List[Dict[str, Any]]:
    many_lists = [levels_to_db_dict(levels_dict, tmk.name, job_id) for tmk, levels_dict in tmk_levels_dict.items()]
    return flatten_collection(many_lists)


def tmk_overall_levels_dict_to_db_dict(tmk_levels_dict: Dict[TradeMetadataKey, Dict[datetime.datetime, float]],
                                       job_id: str) -> List[Dict[str, Any]]:
    many_lists = [overall_levels_to_db_dict(levels_dict, tmk.name, job_id)
                  for tmk, levels_dict in tmk_levels_dict.items()]
    return flatten_collection(many_lists)


def overall_levels_to_db_dict(levels_dict: Dict[datetime.datetime, float],
                              level_type: str, job_id: str) -> List[Dict[str, Any]]:
    """Mimics levels_to_db_dict, but for values that are not for individual agents."""
    return [{'period': period,
             'job_id': job_id,
             'agent': NOT_AN_AGENT,  # Need to set this since the agent field is not nullable
             'type': level_type,
             'level': level}
            for period, level in levels_dict.items()]


def db_to_viewable_level_df_by_agent(job_id: str, agent_guid: str, level_type: str,
                                     session_generator: Callable[[], _GeneratorContextManager[Session]]
                                     = session_scope) -> pd.DataFrame:
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
            return pd.DataFrame(columns=['period', 'level'])


def db_to_viewable_level_df(job_id: str, level_type: str,
                            session_generator: Callable[[], _GeneratorContextManager[Session]]
                            = session_scope) -> pd.DataFrame:
    """
    Mimics db_to_viewable_level_df_by_agent, but for values that are not for individual agents.
    """
    with session_generator() as db:
        levels = db.query(Level).filter(Level.job_id == job_id,
                                        Level.type == level_type).all()

        if len(levels) > 0:
            return pd.DataFrame.from_records([{'period': level.period,
                                               'level': level.level
                                               } for level in levels], index='period')
        else:
            return pd.DataFrame(columns=['period', 'level'])


def sum_levels(job_id: str, level_type: str,
               session_generator: Callable[[], _GeneratorContextManager[Session]] = session_scope) -> float:
    with session_generator() as db:
        rows = db.query(func.sum(Level.level)).filter(Level.job_id == job_id, Level.type == level_type).all()
        if len(rows) > 0 and len(rows[0]) > 0:
            return rows[0][0] if rows[0][0] is not None else 0.0
        return 0.0
