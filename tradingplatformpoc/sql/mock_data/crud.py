import json
import logging
from contextlib import _GeneratorContextManager
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

import polars as pl

from sqlalchemy import Float, and_, select

from sqlmodel import Session

from tradingplatformpoc.connection import session_scope
from tradingplatformpoc.sql.agent.models import Agent
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
    return {'agent_id': db_agent_id,
            'mock_data_constants': mock_data_constants,
            'mock_data': agent_mock_data_binary}


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
    Get mock data for agent_ids and mock data constants. The returned dict has mock data ID as key, agent ID as value.
    """
    with session_generator() as db:

        # Mock data for agents in config with same mock data constants
        res = db.query(MockData.id, MockData.mock_data_constants, MockData.agent_id).filter(
            MockData.agent_id.in_(agent_ids)).all()
        
        return {element.id: element.agent_id for element in res
                if (len(list(set(mock_data_constants.items()) - set(element.mock_data_constants.items()))) == 0)}


def get_mock_data_ids_for_agent(agent_id: str,
                                session_generator: Callable[[], _GeneratorContextManager[Session]]
                                = session_scope) -> List[str]:

    with session_generator() as db:
        res = db.query(MockData.id).filter(MockData.agent_id == agent_id).all()
        return [mock_data_id for (mock_data_id,) in res]


def check_if_agent_equivalent_in_db(agent_config: Dict[str, Any], mock_data_constants: Dict[str, Any],
                                    session_generator: Callable[[], _GeneratorContextManager[Session]]
                                    = session_scope) -> Optional[Dict[str, str]]:
    """
    Is there an 'equivalent', in the mock-data-generating sense, for which we have already generated mock data?
    If there is, the function will return a dict with 2 entries:
    'agent_id' which keeps the ID of the agent which was found to be equivalent to the input agent
    'mock_data_id' which keeps the mock data ID, which can be reused for the input agent
    """
    # Only some parts of the agent configuration is relevant for mock data generation
    input_agent = get_relevant_agent_config(agent_config)

    # Which mock data constants are relevant?
    relevant_mdc_keys = get_relevant_mdc_keys(input_agent, mock_data_constants)
    relevant_mdc = {k: v for k, v in mock_data_constants.items() if k in relevant_mdc_keys}

    # Look at agents for which
    # 1. We have generated mock data
    # 2. The relevant mock data constants match
    # 3. The relevant parts of agent config match

    # Build conditions based on mock data constants:
    conditions = []
    for key, value in relevant_mdc.items():
        conditions.append(MockData.mock_data_constants[key].astext.cast(Float) == value)
    mock_data_constants_conditions = and_(*conditions)

    # Build conditions based on agent config:
    conditions = []
    for key, value in input_agent.items():
        conditions.append(Agent.agent_config[key].astext.cast(Float) == value)
    agent_config_conditions = and_(*conditions)

    with session_generator() as db:
        agent_in_db = db.execute(select(Agent.id,
                                        Agent.agent_config,
                                        MockData.id.label('mock_data_id'),
                                        MockData.mock_data_constants)
                                 .join(MockData, Agent.id == MockData.agent_id)
                                 .where(Agent.agent_type == 'BlockAgent',
                                        mock_data_constants_conditions,
                                        agent_config_conditions)).first()

        if agent_in_db is not None:
            logger.info('Agent equivalent found in db with id {}'.format(agent_in_db.id))
            return {'agent_id': agent_in_db.id, 'mock_data_id': agent_in_db.mock_data_id}
        return None


def get_relevant_agent_config(agent_config: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only the fields used for mock data generation"""
    fields_used = ['Atemp', 'FractionCommercial', 'FractionSchool', 'FractionOffice']
    return {k: v for k, v in agent_config.items() if k in fields_used}


def get_relevant_mdc_keys(input_agent: Dict[str, Any], mock_data_constants: Dict[str, Any]) -> List[str]:
    """
    If an agent only consists of residential buildings, for example, then the commercial, school etc. constants are
    irrelevant.
    """
    relevant_mdc_keys = ['RelativeErrorStdDev']
    for area_type in ['Commercial', 'Office', 'School']:
        if input_agent['Fraction' + area_type] > 0:
            relevant_mdc_keys = relevant_mdc_keys + [mdc_key for mdc_key in mock_data_constants.keys()
                                                     if area_type in mdc_key]
    if input_agent['FractionCommercial'] + input_agent['FractionOffice'] + input_agent['FractionSchool'] < 1:
        relevant_mdc_keys = relevant_mdc_keys + [mdc_key for mdc_key in mock_data_constants.keys()
                                                 if 'Residential' in mdc_key]
    return relevant_mdc_keys
