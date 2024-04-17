# This share of high-temp heat need can be covered by low-temp heat (source: BDAB). The rest needs to be covered by
# a booster heat pump.
PERC_OF_HT_COVERABLE_BY_LT = 0.6


class CEMSError(Exception):
    agent_indices: list[int]
    hour_indices: list[int]

    def __init__(self, message: str, agent_indices: list[int], hour_indices: list[int]):
        self.message = message
        self.agent_indices = agent_indices
        self.hour_indices = hour_indices
