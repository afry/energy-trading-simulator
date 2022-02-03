import datetime
from calendar import isleap, monthrange

MARGINAL_PRICE_WINTER = 0.55
MARGINAL_PRICE_SUMMER = 0.33

EFFECT_PRICE = 74
GRID_FEE_TOP_BRACKET_FIXED = 33750
GRID_FEE_TOP_BRACKET_MARGINAL = 938

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
    return GRID_FEE_TOP_BRACKET_MARGINAL / hours_in_jan_feb
