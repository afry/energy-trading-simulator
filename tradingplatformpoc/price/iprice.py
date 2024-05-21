import datetime
from abc import ABC, abstractmethod
from calendar import monthrange
from typing import Dict, Optional

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

    def __init__(self, resource: Resource):
        self.resource = resource
        self.wholesale_offset = 0
        self.tax = 0
        self.grid_fee = 0
        self.all_external_sells = EMPTY_DATETIME_INDEXED_SERIES.copy()
        self.external_sells_by_agent: Dict[str, pd.Series] = {}

    @abstractmethod
    def get_estimated_retail_price(self, period: datetime.datetime, include_tax: bool) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to sell energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        pass

    @abstractmethod
    def get_estimated_wholesale_price(self, period: datetime.datetime) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to buy energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        pass

    @abstractmethod
    def get_exact_retail_price(self, period: datetime.datetime, include_tax: bool) -> float:
        """Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh"""
        pass

    @abstractmethod
    def get_exact_wholesale_price(self, period: datetime.datetime) -> float:
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""
        pass

    def get_external_grid_buy_price(self, period: datetime.datetime):
        wholesale_price = self.get_estimated_wholesale_price(period)

        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325, Varberg Energi can pay an extra
        # remuneration on top of the Nordpool spot price. This can vary, "depending on for example membership".
        # Might make sense to make this number configurable.
        remuneration_modifier = 0

        return wholesale_price + remuneration_modifier

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

    def get_sells(self, agent: Optional[str] = None) -> pd.Series:
        if agent is not None:
            return self.external_sells_by_agent[agent]
        return self.all_external_sells


def get_days_in_month(month_of_year: int, year: int) -> int:
    return monthrange(year, month_of_year)[1]


def add_to_series(dt_series: pd.Series, period: datetime.datetime, external_heating_sell_quantity: float) -> pd.Series:
    """
    Add to a datetime-indexed series.
    Note: When there is 0 heating sold, this still needs to be added as a value - if there are values "missing" in
    self.all_external_heating_sells, then some methods will break (calculate_jan_feb_avg_heating_sold for example)
    """
    if period in dt_series.index:
        dt_series[period] = dt_series[period] + external_heating_sell_quantity
    else:
        to_add_in = pd.Series(external_heating_sell_quantity, index=[period])
        dt_series = pd.concat([dt_series, to_add_in])
    return dt_series
