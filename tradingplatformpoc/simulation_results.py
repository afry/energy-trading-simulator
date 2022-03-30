import datetime
from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.bid import Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.extra_cost import ExtraCost


@dataclass(frozen=True)
class SimulationResults:
    clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]]
    all_trades: pd.DataFrame
    all_bids: pd.DataFrame
    all_extra_costs: List[ExtraCost]
    storage_levels_dict: Dict[str, Dict[datetime.datetime, float]]
    heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]]
    config_data: Dict[str, Any]
    agents: List[IAgent]
    data_store: DataStore
