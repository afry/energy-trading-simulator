import json
import logging
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List

import pandas as pd

import polars as pl

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.mock_data.models import MockData


logger = logging.getLogger(__name__)


def mock_data_df_to_db_dict(db_agent_id: str, mock_data_constants: Dict[str, float],
                            agent_mock_data_pl: pl.DataFrame):
    """
    Convert mock data from dataframe to binary in order to store in database.
    """
    agent_mock_data_df = agent_mock_data_pl.to_pandas().set_index('datetime')
    agent_mock_data_df.index = agent_mock_data_df.index.strftime('%Y-%m-%d %H:%M:%S.%f')
    agent_mock_data_dict = agent_mock_data_df.to_dict()
    agent_mock_data_binary = json.dumps(agent_mock_data_dict).encode('utf-8')
    dict = {'agent_id': db_agent_id,
            'mock_data_constants': mock_data_constants,
            'mock_data': agent_mock_data_binary}
    return dict


def db_to_mock_data_df(mock_data_id: str,
                       session_generator: Callable[[], _GeneratorContextManager[Session]]
                       = session_scope) -> pl.DataFrame:
    """
    Get mock data for agent_id and mock data constants
    """
    with session_generator() as db:

        # Mock data for agents in config with same mock data constants
        mock_data = db.query(MockData.mock_data).filter(MockData.id == mock_data_id).first()
        
        if mock_data is not None:
            mock_data_dict = json.loads(mock_data[0].decode('utf-8'))
            mock_data_df = pd.DataFrame.from_records(mock_data_dict)
            mock_data_df.index = pd.to_datetime(mock_data_df.index, utc=True)
            mock_data_df = mock_data_df.reset_index().rename(columns={'index': 'datetime'})
            return pl.from_pandas(mock_data_df)
        else:
            raise Exception('No mock data found in database for ID {}'.format(mock_data_id))


def get_mock_data_agent_pairs_in_db(agent_ids: List[str], mock_data_constants: Dict[str, Any],
                                    session_generator: Callable[[], _GeneratorContextManager[Session]]
                                    = session_scope) -> Dict[str, str]:
    """
    Get mock data for agent_ids and mock data constants
    """
    with session_generator() as db:

        # Mock data for agents in config with same mock data constants
        res = db.query(MockData.id, MockData.mock_data_constants, MockData.agent_id).filter(
            MockData.agent_id.in_(agent_ids)).all()
        
        return {element.id: element.agent_id for element in res
                if (len(list(set(mock_data_constants.items()) - set(element.mock_data_constants.items()))) == 0)}


def get_mock_data_ids_for_agent(agent_id: str,
                                session_generator: Callable[[], _GeneratorContextManager[Session]]
                                = session_scope) -> Dict[str, str]:

    with session_generator() as db:
        res = db.query(MockData.id).filter(MockData.agent_id == agent_id).all()
        return [mock_data_id for (mock_data_id,) in res]
