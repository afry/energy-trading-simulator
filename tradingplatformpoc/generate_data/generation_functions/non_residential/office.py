import datetime

from tradingplatformpoc.generate_data.generation_functions.common import is_day_before_major_holiday_sweden, \
    is_major_holiday_sweden
from tradingplatformpoc.generate_data.generation_functions.non_residential.common import \
    get_cooling_month_scaling_factor


def get_office_heating_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    """Assuming opening hours 8-17:00 except for weekends and breaks"""
    if timestamp.weekday() == 5 or timestamp.weekday() == 6:  # Saturday or sunday
        return 0.5
    if is_major_holiday_sweden(timestamp):
        return 0.5
    if is_day_before_major_holiday_sweden(timestamp):
        return 0.5
    if not (8 <= timestamp.hour < 17):
        return 0.5
    return 1.0


def get_office_cooling_consumption_factor(timestamp: datetime.datetime) -> float:
    """Returns a dimensionless scaling factor for cooling."""
    return (get_cooling_month_scaling_factor(timestamp.month)
            * get_office_heating_consumption_hourly_factor(timestamp))
