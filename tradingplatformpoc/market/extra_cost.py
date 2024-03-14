import datetime
from enum import Enum


class ExtraCostType(Enum):
    HEAT_EXT_COST_CORR = 0


class ExtraCost:
    period: datetime.datetime
    agent: str
    cost_type: ExtraCostType
    cost: float

    def __init__(self, period: datetime.datetime, agent: str, cost_type: ExtraCostType, cost: float) -> None:
        self.period = period
        self.agent = agent
        self.cost_type = cost_type
        self.cost = cost
