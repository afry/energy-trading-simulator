import datetime
import logging
from calendar import isleap, monthrange
from typing import Dict

import numpy as np

import pandas as pd

from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.price.iprice import IPrice

EFFECT_PRICE = 74

GRID_FEE_MARGINAL_SUB_50 = 1113
GRID_FEE_FIXED_SUB_50 = 1150
GRID_FEE_MARGINAL_50_100 = 1075
GRID_FEE_FIXED_50_100 = 3063
GRID_FEE_MARGINAL_100_200 = 1025
GRID_FEE_FIXED_100_200 = 8163
GRID_FEE_MARGINAL_200_400 = 975
GRID_FEE_FIXED_200_400 = 18375
GRID_FEE_FIXED_400_PLUS = 33750
GRID_FEE_MARGINAL_400_PLUS = 938

MARGINAL_PRICE_WINTER = 0.55
MARGINAL_PRICE_SUMMER = 0.33

logger = logging.getLogger(__name__)

"""
For a more thorough explanation of the district heating pricing mechanism, see
https://doc.afdrift.se/display/RPJ/District+heating+Varberg%3A+Pricing
"""


def estimate_district_heating_price(period: datetime.datetime) -> float:
    """
    Three price components:
    * "Energy price" or "base marginal price"
    * "Grid fee" based on consumption in January+February
    * "Effect fee" based on the "peak day" of the month
    """
    effect_fee = expected_effect_fee(period)
    jan_feb_extra = marginal_grid_fee_assuming_top_bracket(period.year)
    base_marginal_price = get_base_marginal_price(period.month)
    return base_marginal_price + effect_fee + (jan_feb_extra * (period.month <= 2))


def probability_day_is_peak_day(period: datetime.datetime) -> float:
    """
    What is the likelihood that a given day, is the 'peak day' of the month? Without knowing past or future
    consumption levels, or looking at outdoor temperature or anything like that, this is the best we can do: Each day of
    the month has the same probability as all the others.
    """
    days_in_month = monthrange(period.year, period.month)[1]
    return 1 / days_in_month


def expected_effect_fee(period: datetime.datetime) -> float:
    """
    Every consumed kWh during the peak day, increases the effect fee by EFFECT_PRICE / 24, since there are 24 hours in a
    day. The expected fee for a given day then becomes:
    E[fee]  = P(day is peak day) * EFFECT_PRICE/24 + P(day is not peak day) * 0
            = P(day is peak day) * EFFECT_PRICE/24
    """
    p = probability_day_is_peak_day(period)
    return (EFFECT_PRICE / 24) * p


def get_base_marginal_price(month_of_year: int) -> float:
    """'Summer price' during May-September, 'Winter price' other months."""
    if 5 <= month_of_year <= 9:
        return MARGINAL_PRICE_SUMMER  # Cheaper in summer
    else:
        return MARGINAL_PRICE_WINTER


def marginal_grid_fee_assuming_top_bracket(year: int) -> float:
    """
    The grid fee is based on the average consumption in kW during January and February.
    Using 1 kWh during January and February, increases the average Jan-Feb consumption by 1 / hours_in_jan_feb.
    The marginal cost depends on what "bracket" one falls into, but we'll assume we always end up in the top bracket.
    More info at https://doc.afdrift.se/display/RPJ/District+heating+Varberg%3A+Pricing
    """
    hours_in_jan_feb = 1416 + (24 if isleap(year) else 0)
    return GRID_FEE_MARGINAL_400_PLUS / hours_in_jan_feb


def exact_district_heating_price_for_month(month: int, year: int, consumption_this_month_kwh: float,
                                           jan_feb_avg_consumption_kw: float,
                                           prev_month_peak_day_avg_consumption_kw: float) -> float:
    """
    Three price components:
    * "Energy price" or "base marginal price"
    * "Grid fee" based on consumption in January+February
    * "Effect fee" based on the "peak day" of the month
    @param month                                    The month one wants the price for.
    @param year                                     The year one wants the price for.
    @param consumption_this_month_kwh               The total amount of heating bought, in kWh, this month.
    @param jan_feb_avg_consumption_kw               The average heating effect bought, in kW, during the previous
                                                        January-February period. This is used to calculate the "grid
                                                        fee" price component.
    @param prev_month_peak_day_avg_consumption_kw   The average heating effect bought, in kW, during the day of the
                                                        previous month when it was the highest. This is used to
                                                        calculate the "effect fee" price component.
    """
    effect_fee = exact_effect_fee(prev_month_peak_day_avg_consumption_kw)
    grid_fee = get_grid_fee_for_month(jan_feb_avg_consumption_kw, year, month)
    base_marginal_price = get_base_marginal_price(month)
    return base_marginal_price * consumption_this_month_kwh + effect_fee + grid_fee


def exact_effect_fee(monthly_peak_day_avg_consumption_kw: float) -> float:
    """
    @param monthly_peak_day_avg_consumption_kw Calculated by taking the day during the month which has the highest
        heating energy use, and taking the average hourly heating use that day.
    """
    return EFFECT_PRICE * monthly_peak_day_avg_consumption_kw


def get_yearly_grid_fee(jan_feb_hourly_avg_consumption_kw: float) -> float:
    """Based on Jan-Feb average hourly heating use."""
    if jan_feb_hourly_avg_consumption_kw < 50:
        return GRID_FEE_FIXED_SUB_50 + GRID_FEE_MARGINAL_SUB_50 * jan_feb_hourly_avg_consumption_kw
    elif jan_feb_hourly_avg_consumption_kw < 100:
        return GRID_FEE_FIXED_50_100 + GRID_FEE_MARGINAL_50_100 * jan_feb_hourly_avg_consumption_kw
    elif jan_feb_hourly_avg_consumption_kw < 200:
        return GRID_FEE_FIXED_100_200 + GRID_FEE_MARGINAL_100_200 * jan_feb_hourly_avg_consumption_kw
    elif jan_feb_hourly_avg_consumption_kw < 400:
        return GRID_FEE_FIXED_200_400 + GRID_FEE_MARGINAL_200_400 * jan_feb_hourly_avg_consumption_kw
    else:
        return GRID_FEE_FIXED_400_PLUS + GRID_FEE_MARGINAL_400_PLUS * jan_feb_hourly_avg_consumption_kw


def get_grid_fee_for_month(jan_feb_hourly_avg_consumption_kw: float, year: int, month_of_year: int) -> float:
    """
    The grid fee is based on the average consumption in kW during January and February.
    This fee is then spread out evenly during the year.
    """
    days_in_month = monthrange(year, month_of_year)[1]
    days_in_year = 366 if isleap(year) else 365
    fraction_of_year = days_in_month / days_in_year
    yearly_fee = get_yearly_grid_fee(jan_feb_hourly_avg_consumption_kw)
    return yearly_fee * fraction_of_year


def calculate_jan_feb_avg_heating_sold(all_external_heating_sells: pd.Series, period: datetime.datetime) -> float:
    """
    Calculates the average effect (in kW) of heating sold in the previous January-February.
    """
    year_we_are_interested_in = period.year - 1 if period.month <= 2 else period.year
    subset = (all_external_heating_sells.index.year == year_we_are_interested_in) & \
             (all_external_heating_sells.index.month <= 2)
    if not any(subset):
        logger.warning("No data to base grid fee on, will 'cheat' and use future data")
        subset = (all_external_heating_sells.index.month <= 2)
    return all_external_heating_sells[subset].mean()


def calculate_peak_day_avg_cons_kw(all_external_heating_sells: pd.Series, year: int, month: int) -> float:
    subset = (all_external_heating_sells.index.year == year) & \
             (all_external_heating_sells.index.month == month)
    heating_sells_this_month = all_external_heating_sells[subset].copy()
    sold_by_day = heating_sells_this_month.groupby(heating_sells_this_month.index.day).sum()
    peak_day_avg_consumption = sold_by_day.max() / 24
    return peak_day_avg_consumption


def handle_no_consumption_when_calculating_heating_price(period):
    logger.warning("Tried to calculate exact external heating price, in SEK/kWh, for {:%B %Y}, but had no "
                   "consumption for this month, so returned np.nan.".format(period))
    return np.nan


class HeatingPrice(IPrice):
    all_external_heating_sells: pd.Series
    heating_wholesale_price_fraction: float
    heat_transfer_loss_per_side: float

    def __init__(self, config_area_info: Dict[str, float]):
        super().__init__(Resource.HEATING)
        self.all_external_heating_sells = pd.Series([], dtype=float, index=pd.to_datetime([], utc=True))
        self.heating_wholesale_price_fraction = config_area_info['ExternalHeatingWholesalePriceFraction']
        # Square root since it is added both to the BUY and the SELL side
        self.heat_transfer_loss_per_side = 1 - np.sqrt(1 - config_area_info["HeatTransferLoss"])

    def get_estimated_retail_price(self, period: datetime.datetime, include_tax: bool) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to sell energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        # District heating is not taxed
        return estimate_district_heating_price(period)

    def get_estimated_wholesale_price(self, period: datetime.datetime) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to buy energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        return estimate_district_heating_price(period) * self.heating_wholesale_price_fraction

    def get_exact_retail_price(self, period: datetime.datetime, include_tax: bool) -> float:
        """Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh"""

        # District heating is not taxed
        consumption_this_month_kwh = self.calculate_consumption_this_month(period.year, period.month)
        if consumption_this_month_kwh == 0:
            return handle_no_consumption_when_calculating_heating_price(period)
        jan_feb_avg_consumption_kw = calculate_jan_feb_avg_heating_sold(self.all_external_heating_sells, period)
        prev_month_peak_day_avg_consumption_kw = calculate_peak_day_avg_cons_kw(self.all_external_heating_sells,
                                                                                period.year, period.month)
        total_cost_for_month = exact_district_heating_price_for_month(period.month, period.year,
                                                                      consumption_this_month_kwh,
                                                                      jan_feb_avg_consumption_kw,
                                                                      prev_month_peak_day_avg_consumption_kw)
        return total_cost_for_month / consumption_this_month_kwh
    
    def get_exact_wholesale_price(self, period: datetime.datetime) -> float:
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""

        consumption_this_month_kwh = self.calculate_consumption_this_month(period.year, period.month)
        if consumption_this_month_kwh == 0:
            return handle_no_consumption_when_calculating_heating_price(period)
        jan_feb_avg_consumption_kw = calculate_jan_feb_avg_heating_sold(self.all_external_heating_sells, period)
        prev_month_peak_day_avg_consumption_kw = calculate_peak_day_avg_cons_kw(self.all_external_heating_sells,
                                                                                period.year, period.month)
        total_cost_for_month = exact_district_heating_price_for_month(period.month, period.year,
                                                                      consumption_this_month_kwh,
                                                                      jan_feb_avg_consumption_kw,
                                                                      prev_month_peak_day_avg_consumption_kw)
        return (total_cost_for_month / consumption_this_month_kwh) * self.heating_wholesale_price_fraction

    def calculate_consumption_this_month(self, year: int, month: int) -> float:
        """
        Calculate the sum of all external heating sells for the specified year-month combination.
        Returns a float with the unit kWh.
        """
        subset = (self.all_external_heating_sells.index.year == year) & \
                 (self.all_external_heating_sells.index.month == month)
        return sum(self.all_external_heating_sells[subset])
    
    def add_external_heating_sell(self, period: datetime.datetime, external_heating_sell_quantity: float):
        """
        The data_store needs this information to be able to calculate the exact district heating cost.
        Note: When there is 0 heating sold, this still needs to be added as a value - if there are values "missing" in
        self.all_external_heating_sells, then some methods will break (calculate_jan_feb_avg_heating_sold for example)
        """
        if period in self.all_external_heating_sells.index:
            existing_value = self.all_external_heating_sells[period]
            logger.warning('Already had a value for external heating sell for period {}. Was {}, will overwrite it '
                           'with new value {}.'.format(period, existing_value, external_heating_sell_quantity))
            self.all_external_heating_sells[period] = external_heating_sell_quantity
        else:
            to_add_in = pd.Series(external_heating_sell_quantity, index=[period])
            self.all_external_heating_sells = pd.concat([self.all_external_heating_sells, to_add_in])
