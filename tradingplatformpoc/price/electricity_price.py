import datetime
import logging
from typing import List, Optional, Union

import pandas as pd

from tradingplatformpoc.market.trade import Market, Resource
from tradingplatformpoc.price.iprice import IPrice, get_days_in_month

logger = logging.getLogger(__name__)


class ElectricityPrice(IPrice):
    nordpool_data: pd.Series
    transmission_fee: float  # SEK/kWh
    effect_fee: float  # SEK/kW for the month
    elec_tax_internal: float  # SEK/kWh
    elec_transmission_fee_internal: float  # SEK/kWh
    elec_effect_fee_internal: float  # SEK/kW

    def __init__(self, elec_wholesale_offset: float,
                 elec_tax: float, elec_transmission_fee: float, elec_effect_fee: float,
                 elec_tax_internal: float, elec_transmission_fee_internal: float, elec_effect_fee_internal: float,
                 nordpool_data: pd.Series):
        super().__init__(Resource.ELECTRICITY)
        self.nordpool_data = nordpool_data
        self.wholesale_offset = elec_wholesale_offset
        self.tax = elec_tax
        self.transmission_fee = elec_transmission_fee
        self.effect_fee = elec_effect_fee
        self.elec_tax_internal = elec_tax_internal
        self.elec_transmission_fee_internal = elec_transmission_fee_internal
        self.elec_effect_fee_internal = elec_effect_fee_internal

        self.grid_fee = self.transmission_fee + self.effect_fee / 8766.0
        self.elec_grid_fee_internal = self.elec_transmission_fee_internal + self.elec_effect_fee_internal / 8766.0
    
    def get_external_gross_retail_price_excl_effect_fee(self, nordpool_price: Union[float, pd.Series]) \
            -> Union[float, pd.Series]:
        """
        The external grid sells at the Nordpool spot price, plus the "transmission fee", plus an effect fee.
        We have decided to use Göteborg Energi's pricing model (outlined at
        https://www.goteborgenergi.se/foretag/elnat/elnatsavgiften), since it is slightly simpler than Varberg Energi's.
        """
        return nordpool_price + self.transmission_fee

    def get_electricity_net_external_price(self, gross_price: Union[float, pd.Series]) -> Union[float, pd.Series]:
        """
        Net external price = gross external price (i.e. what the seller receives) + tax
        """
        return gross_price + self.tax

    def get_electricity_wholesale_price_from_nordpool_price(self, nordpool_price: Union[float, pd.Series]) \
            -> Union[float, pd.Series]:
        """
        Wholesale price = Nordpool spot price + self.elec_wholesale_offset
        """
        return nordpool_price + self.wholesale_offset

    def get_exact_retail_price(self, period: datetime.datetime, include_tax: bool, agent: Optional[str] = None) \
            -> float:
        """
        Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh.
        Only using external prices - will not work for "internal" prices.
        """
        sells_series = self.get_sells(agent)
        effect_fee_per_kwh = calculate_effect_fee_per_kwh(sells_series, self.effect_fee, period)
        nordpool_price = self.get_nordpool_price_for_periods(period)
        return nordpool_price + self.transmission_fee + effect_fee_per_kwh + (self.tax if include_tax else 0.0)

    def get_exact_wholesale_price(self, period: datetime.datetime, agent: Optional[str] = None) -> float:
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""
        nordpool_price = self.get_nordpool_price_for_periods(period)
        return self.get_electricity_wholesale_price_from_nordpool_price(nordpool_price)

    def get_nordpool_price_for_periods(self, start_period: datetime.datetime, length: int = 1) \
            -> Union[float, pd.Series]:
        if length == 1:
            return self.nordpool_data.loc[start_period]
        start_index = self.nordpool_data.index.get_loc(start_period)
        end_index = start_index + length
        return self.nordpool_data.iloc[start_index:end_index]

    def get_tax(self, market: Market) -> float:
        return self.elec_tax_internal if market == Market.LOCAL else self.tax

    def get_grid_fee(self, market: Market) -> float:
        return self.elec_grid_fee_internal if market == Market.LOCAL else self.grid_fee

    def get_effect_fee_per_day(self, date_time: datetime.datetime) -> float:
        return self.effect_fee / get_days_in_month(date_time.month, date_time.year)

    def get_top_three_hourly_outtakes_for_month(self, period: datetime.datetime, agent: Optional[str] = None) \
            -> List[float]:
        """
        This method will fetch the top 3 hourly outtakes for the month - but if it is early in the month, it will also
        look at the previous month's values.
        """
        sells_series = self.get_sells(agent)
        top_3_this_month = calculate_top_three_hourly_outtakes_for_month(sells_series, period.year, period.month)
        at_least_n_days = 5
        if period.day < at_least_n_days:
            # Early in the month, we'll also use last month's values, so that we don't underestimate.
            # We will scale those values a bit though, so that we don't overestimate.
            scale_factor_for_last_month = 0.8
            prev_month = period - datetime.timedelta(days=at_least_n_days + 1)
            top_3_last_month = calculate_top_three_hourly_outtakes_for_month(sells_series,
                                                                             prev_month.year, prev_month.month)
            scaled_last_month = [value * scale_factor_for_last_month for value in top_3_last_month]
            # Combine the lists
            combined_values = top_3_this_month + scaled_last_month
            # Find the top 3 highest values
            top_3 = sorted(combined_values, reverse=True)[:3]
        else:
            top_3 = top_3_this_month

        # Pad with 0s if there are less than 3 values
        top_3 += [0] * (3 - len(top_3))
        return top_3


def calculate_top_three_hourly_outtakes_for_month(dt_series: pd.Series, year: int, month: int) -> List[float]:
    """
    iven a series with a DatetimeIndex and numerical values, calculate the top 3 hourly outtakes for the given month.
    Used in Göteborg Energi's pricing model to calculate the effect fee.
    """
    subset = (dt_series.index.year == year) & (dt_series.index.month == month)
    return dt_series[subset].nlargest(3).values.tolist()


def calculate_total_for_month(dt_series: pd.Series, year: int, month: int) -> float:
    """
    Given a series with a DatetimeIndex and numerical values, calculate the total for the given month.
    """
    subset = (dt_series.index.year == year) & (dt_series.index.month == month)
    return dt_series[subset].sum()


def get_value_for_period(dt_series: pd.Series, dt: datetime.datetime) -> float:
    """
    Given a series with a DatetimeIndex and numerical values, get the value for the given datetime, if it exists, else
    return 0.
    """
    return dt_series.get(dt, 0.0)


def calculate_effect_fee_per_kwh(sells_series: pd.Series, effect_fee: float, dt: datetime.datetime) -> float:
    top_3 = calculate_top_three_hourly_outtakes_for_month(sells_series, dt.year, dt.month)
    avg_elec_peak_load = sum(top_3) / 3.0
    effect_fee_for_month = avg_elec_peak_load * effect_fee
    total_bought_this_month = calculate_total_for_month(sells_series, dt.year, dt.month)
    if total_bought_this_month > 0:
        return effect_fee_for_month / total_bought_this_month
    else:
        return 0.0
