import json
from typing import Dict

import pandas as pd

from tradingplatformpoc.sql.mock_data.models import MockData


def mock_data_to_db_object(db_agent_id: str, mock_data_constants: Dict[str, float],
                           agent_mock_data_df: pd.DataFrame):
    """
    Convert mock data from dataframe to binary in order to store in database.
    """
    agent_mock_data_df.index = agent_mock_data_df.index.strftime('%Y-%m-%d %H:%M:%S.%f')
    agent_mock_data_dict = agent_mock_data_df.to_dict()
    agent_mock_data_binary = json.dumps(agent_mock_data_dict).encode('utf-8')
    return MockData(db_agent_id, mock_data_constants, agent_mock_data_binary)
