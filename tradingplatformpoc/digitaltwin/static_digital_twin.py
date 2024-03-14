import logging
from typing import Optional

import pandas as pd

from tradingplatformpoc.market.trade import Resource

logger = logging.getLogger(__name__)


def get_value_or_zero(period, series: pd.Series):
    return 0 if series is None else series.loc[period]


def add_series_or_none(series_1: Optional[pd.Series], series_2: Optional[pd.Series]) -> (
        Optional)[pd.Series]:
    if series_1 is None:
        if series_2 is None:
            return None
        return series_2
    if series_2 is None:
        return series_1
    return series_1 + series_2


class StaticDigitalTwin:
    """
    A static digital twin is a representation of a physical asset where energy production and consumption are "static",
    i.e. are defined when initializing the digital twin, and never change after that.
    Not specifying a Series when initializing the class will make it assume it is 0.
    """
    gross_floor_area: float
    electricity_usage: pd.Series
    space_heating_usage: pd.Series
    hot_water_usage: pd.Series
    cooling_usage: pd.Series
    electricity_production: pd.Series
    space_heating_production: pd.Series
    hot_water_production: pd.Series
    cooling_production: pd.Series
    total_heating_usage: pd.Series
    total_heating_production: pd.Series

    def __init__(self, gross_floor_area: float, electricity_usage: pd.Series = None,
                 space_heating_usage: pd.Series = None, hot_water_usage: pd.Series = None,
                 cooling_usage: pd.Series = None, electricity_production: pd.Series = None,
                 space_heating_production: pd.Series = None, hot_water_production: pd.Series = None,
                 cooling_production: pd.Series = None):
        self.gross_floor_area = gross_floor_area
        self.electricity_usage = electricity_usage
        self.space_heating_usage = space_heating_usage
        self.hot_water_usage = hot_water_usage
        self.cooling_usage = cooling_usage
        self.electricity_production = electricity_production
        self.space_heating_production = space_heating_production
        self.hot_water_production = hot_water_production
        self.cooling_production = cooling_production
        # To be removed:
        self.total_heating_usage = add_series_or_none(space_heating_usage, hot_water_usage)
        self.total_heating_production = add_series_or_none(space_heating_production, hot_water_production)

    def get_production(self, period, resource: Resource) -> float:
        if resource == Resource.ELECTRICITY:
            return get_value_or_zero(period, self.electricity_production)
        elif resource == Resource.HEATING:
            return (get_value_or_zero(period, self.space_heating_production)
                    + get_value_or_zero(period, self.hot_water_production))
        elif resource == Resource.COOLING:
            return get_value_or_zero(period, self.cooling_production)
        elif resource == Resource.LOW_TEMP_HEAT:
            return get_value_or_zero(period, self.space_heating_production)
        elif resource == Resource.HIGH_TEMP_HEAT:
            return get_value_or_zero(period, self.hot_water_production)
        else:
            logger.warning("No production defined for resource {}".format(resource))
            return 0

    def get_consumption(self, period, resource: Resource) -> float:
        if resource == Resource.ELECTRICITY:
            return get_value_or_zero(period, self.electricity_usage)
        elif resource == Resource.HEATING:
            return get_value_or_zero(period, self.space_heating_usage) + get_value_or_zero(period, self.hot_water_usage)
        elif resource == Resource.COOLING:
            return get_value_or_zero(period, self.cooling_usage)
        elif resource == Resource.LOW_TEMP_HEAT:
            return get_value_or_zero(period, self.space_heating_usage)
        elif resource == Resource.HIGH_TEMP_HEAT:
            return get_value_or_zero(period, self.hot_water_usage)
        else:
            logger.warning("No usage defined for resource {}".format(resource))
            return 0
