import datetime
from enum import Enum

import pandas as pd

from tradingplatformpoc.bid import Resource


class ExtraCostType(Enum):
    ELEC_BID_INACCURACY = 0
    HEAT_BID_INACCURACY = 1
    HEAT_EXT_COST_CORR = 2

    def is_for_bid_inaccuracy(self) -> bool:
        return self in [ExtraCostType.ELEC_BID_INACCURACY, ExtraCostType.HEAT_BID_INACCURACY]


def get_extra_cost_type_for_bid_inaccuracy(resource: Resource) -> ExtraCostType:
    if resource == Resource.ELECTRICITY:
        return ExtraCostType.ELEC_BID_INACCURACY
    elif resource == Resource.HEATING:
        return ExtraCostType.HEAT_BID_INACCURACY
    else:
        raise RuntimeError('Method not implemented for {}'.format(resource))


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

    def __str__(self):
        """Creates a CSV string."""
        return "{},{},{},{}".format(self.period, self.agent, self.cost_type, self.cost)

    def to_series(self) -> pd.Series:
        return pd.Series(data={'period': self.period,
                               'agent': self.agent,
                               'cost_type': self.cost_type,
                               'cost': self.cost})
