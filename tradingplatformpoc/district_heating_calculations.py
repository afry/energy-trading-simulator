import datetime
from calendar import isleap, monthrange

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
    #print("effect_fee = ", effect_fee)
    grid_fee = get_grid_fee_for_month(jan_feb_avg_consumption_kw, year, month)
    #print("grid_fee = ", grid_fee)
    base_marginal_price = get_base_marginal_price(month)
    #print("base_marginal_price = ", base_marginal_price)
    #print("exact_price = ", base_marginal_price * consumption_this_month_kwh + effect_fee + grid_fee)
    #print("--------------------------------------------------")
    return effect_fee, grid_fee, base_marginal_price, base_marginal_price * consumption_this_month_kwh + effect_fee + grid_fee


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
