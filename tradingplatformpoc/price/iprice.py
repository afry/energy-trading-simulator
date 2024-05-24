import datetime
from abc import ABC, abstractmethod
from calendar import monthrange
from typing import Dict, Optional

import numpy as np

import pandas as pd

from tradingplatformpoc.market.trade import Resource

EMPTY_DATETIME_INDEXED_SERIES = pd.Series([], dtype=float, index=pd.to_datetime([], utc=True))


class IPrice(ABC):
    resource: Resource
    transfer_loss_per_side: float
    wholesale_offset: float
    tax: float  # SEK/kWh
    grid_fee: float  # SEK/kWh
    all_external_sells: pd.Series
    external_sells_by_agent: Dict[str, pd.Series]
    price_estimates: pd.Series
    price_estimates_by_agent: Dict[str, pd.Series]

    def __init__(self, resource: Resource):
        self.resource = resource
        self.wholesale_offset = 0
        self.tax = 0
        self.grid_fee = 0
        self.all_external_sells = EMPTY_DATETIME_INDEXED_SERIES.copy()
        self.external_sells_by_agent: Dict[str, pd.Series] = {}
        self.price_estimates = EMPTY_DATETIME_INDEXED_SERIES.copy()
        self.price_estimates_by_agent: Dict[str, pd.Series] = {}

    @abstractmethod
    def get_exact_retail_price(self, period: datetime.datetime, include_tax: bool, agent: Optional[str] = None) \
            -> float:
        """Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh"""
        pass

    @abstractmethod
    def get_exact_wholesale_price(self, period: datetime.datetime, agent: Optional[str] = None) -> float:
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""
        pass

    def add_external_sell(self, period: datetime.datetime, external_sell_quantity: float):
        """
        We need this information to be able to calculate the exact cost.
        """
        self.all_external_sells = add_to_series(self.all_external_sells, period, external_sell_quantity)

    def add_external_sell_for_agent(self, period: datetime.datetime, external_sell_quantity: float, agent_id: str):
        """
        We need this information to be able to calculate the exact cost.
        """
        if agent_id not in self.external_sells_by_agent.keys():
            self.external_sells_by_agent[agent_id] = EMPTY_DATETIME_INDEXED_SERIES.copy()
        self.external_sells_by_agent[agent_id] = add_to_series(
            self.external_sells_by_agent[agent_id], period, external_sell_quantity)

    def add_price_estimate(self, period: datetime.datetime, price_estimate: float):
        """
        We need this information to be able to calculate cost corrections later.
        """
        self.price_estimates = set_in_series(self.price_estimates, period, price_estimate)

    def add_price_estimate_for_agent(self, period: datetime.datetime, price_estimate: float, agent_id: str):
        """
        We need this information to be able to calculate cost corrections later.
        """
        if agent_id not in self.price_estimates_by_agent.keys():
            self.price_estimates_by_agent[agent_id] = EMPTY_DATETIME_INDEXED_SERIES.copy()
        self.price_estimates_by_agent[agent_id] = set_in_series(
            self.price_estimates_by_agent[agent_id], period, price_estimate)

    def get_retail_price_estimate(self, period: datetime.datetime, agent: Optional[str]) \
            -> float:
        if agent is not None:
            if agent in self.price_estimates_by_agent.keys():
                return self.price_estimates_by_agent[agent].get(period, np.nan)
            return np.nan
        return self.price_estimates.get(period, np.nan)

    def get_sells(self, agent: Optional[str] = None) -> pd.Series:
        if agent is not None:
            if agent in self.external_sells_by_agent.keys():
                return self.external_sells_by_agent[agent]
            return EMPTY_DATETIME_INDEXED_SERIES.copy()
        return self.all_external_sells


def get_days_in_month(month_of_year: int, year: int) -> int:
    return monthrange(year, month_of_year)[1]


def add_to_series(dt_series: pd.Series, period: datetime.datetime, quantity: float) -> pd.Series:
    """
    Add to a datetime-indexed series.
    Note: When there is 0 heating sold, this still needs to be added as a value - if there are values "missing" in
    self.all_external_heating_sells, then some methods will break (calculate_jan_feb_avg_heating_sold for example)
    """
    if period in dt_series.index:
        dt_series[period] = dt_series[period] + quantity
    else:
        to_add_in = pd.Series(quantity, index=[period])
        dt_series = pd.concat([dt_series, to_add_in])
    return dt_series


def set_in_series(dt_series: pd.Series, period: datetime.datetime, value: float) -> pd.Series:
    """
    Set a value in a datetime-indexed series, raising an error if a value already exists.
    """
    if period in dt_series.index:
        raise ValueError('Tried to overwrite value for period {}'.format(period))
    to_add_in = pd.Series(value, index=[period])
    dt_series = pd.concat([dt_series, to_add_in])
    return dt_series
