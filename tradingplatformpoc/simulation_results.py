import datetime
from dataclasses import dataclass
from typing import Any, Collection, Dict, List

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.bid import BidWithAcceptanceStatus, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.extra_cost import ExtraCost
from tradingplatformpoc.trade import Trade


@dataclass(frozen=True)
class SimulationResults:
    clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]]
    all_trades_dict: Dict[datetime.datetime, Collection[Trade]]
    all_bids_dict: Dict[datetime.datetime, Collection[BidWithAcceptanceStatus]]
    all_extra_costs: List[ExtraCost]
    storage_levels_dict: Dict[str, Dict[datetime.datetime, float]]
    heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]]
    config_data: Dict[str, Any]
    agents: List[IAgent]
    data_store: DataStore
