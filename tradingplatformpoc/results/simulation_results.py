import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pandas as pd

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.results.results_key import ResultsKey


@dataclass(frozen=True)
class SimulationResults:
    clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]]
    all_trades: pd.DataFrame
    all_bids: pd.DataFrame
    all_extra_costs: pd.DataFrame
    storage_levels_dict: Dict[str, Dict[datetime.datetime, float]]
    heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]]
    config_data: Dict[str, Any]
    agents: List[IAgent]
    data_store: DataStore
    grid_fees_paid_on_internal_trades: float
    tax_paid: float
    exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]
    exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]
    results_by_agent: Dict[str, Dict[ResultsKey, float]]
