import logging

import pandas as pd

from tradingplatformpoc.market.bid import Resource

logger = logging.getLogger(__name__)


def get_value_or_zero(period, series: pd.Series):
    return 0 if series is None else series.loc[period]


class StaticDigitalTwin:
    """
    A static digital twin is a representation of a physical asset where energy production and consumption are "static",
    i.e. are defined when initializing the digital twin, and never change after that.
    Not specifying a Series when initializing the class will make it assume it is 0.
    """

    def __init__(self, electricity_usage: pd.Series = None, heating_usage: pd.Series = None,
                 electricity_production: pd.Series = None, heating_production: pd.Series = None):
        self.electricity_usage = electricity_usage
        self.heating_usage = heating_usage
        self.electricity_production = electricity_production
        self.heating_production = heating_production

    def get_production(self, period, resource: Resource) -> float:
        if resource == Resource.ELECTRICITY:
            return get_value_or_zero(period, self.electricity_production)
        elif resource == Resource.HEATING:
            return get_value_or_zero(period, self.heating_production)
        else:
            logger.warning("No production defined for resource {}".format(resource))
            return 0

    def get_consumption(self, period, resource: Resource) -> float:
        if resource == Resource.ELECTRICITY:
            return get_value_or_zero(period, self.electricity_usage)
        elif resource == Resource.HEATING:
            return get_value_or_zero(period, self.heating_usage)
        else:
            logger.warning("No usage defined for resource {}".format(resource))
            return 0
