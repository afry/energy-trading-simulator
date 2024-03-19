import datetime

from tradingplatformpoc.generate_data.generation_functions.non_residential.common import \
    get_cooling_month_scaling_factor

COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR = {
    0: 0.2,
    1: 0.2,
    2: 0.2,
    3: 0.2,
    4: 0.2,
    5: 0.2,
    6: 0.3,
    7: 0.5,
    8: 0.7,
    9: 0.91,
    10: 0.92,
    11: 0.93,
    12: 0.94,
    13: 0.95,
    14: 0.96,
    15: 0.97,
    16: 0.98,
    17: 0.99,
    18: 1.0,
    19: 0.6,
    20: 0.2,
    21: 0.2,
    22: 0.2,
    23: 0.2
}


def get_commercial_electricity_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    return COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR[timestamp.hour]


def get_commercial_heating_consumption_hourly_factor(timestamp: datetime.datetime) -> float:
    """Assuming opening hours 9-20, roughly similar to COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR"""
    if 9 <= timestamp.hour < 20:
        return 1.0
    else:
        return 0.5


def get_commercial_cooling_consumption_factor(timestamp: datetime.datetime) -> float:
    """Returns a dimensionless scaling factor for cooling."""
    return (get_cooling_month_scaling_factor(timestamp.month)
            * COMMERCIAL_ELECTRICITY_CONSUMPTION_HOURLY_FACTOR[timestamp.hour])
