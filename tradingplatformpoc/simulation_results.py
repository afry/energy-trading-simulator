import datetime
from dataclasses import dataclass
from typing import Any, Collection, Dict, List, Tuple

from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.bid import BidWithAcceptanceStatus, Resource
from tradingplatformpoc.extra_cost import ExtraCost
from tradingplatformpoc.trade import Trade


@dataclass(frozen=True)
class SimulationResults:
    clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]]
    all_trades_dict: Dict[datetime.datetime, Collection[Trade]]
    all_bids_dict: Dict[datetime.datetime, Collection[BidWithAcceptanceStatus]]
    all_extra_costs: List[ExtraCost]
    storage_levels_dict: Dict[Tuple[datetime.datetime, str], float]
    heat_pump_levels_dict: Dict[Tuple[datetime.datetime, str], float]
    config_data: Dict[str, Any]
    agents: List[IAgent]
