import datetime
from typing import Optional, Tuple

import pandas as pd

from tradingplatformpoc.trading_platform_utils import should_use_summer_mode


def _get_grocery_store_hourly_factor(timestamp: datetime.datetime) -> float:
    """
    Assuming opening hours 8-22 every day.
    See also 'docs/Heat production.md'
    """
    if should_use_summer_mode(timestamp):
        if 8 <= timestamp.hour < 22:
            return 1.0
        else:
            return 0.75
    return 0.0


def _get_grocery_store_max_prod(size_atemp_sqm: float) -> float:
    """
    Assuming that a size of 6000 sqm leads to a max production of 80 kW, scaling linearly.
    See also 'docs/Heat production.md'
    """
    return (size_atemp_sqm / 6000.0) * 80.0


def _grocery_store_heat_production(datetimes: pd.DatetimeIndex, size_atemp_sqm: float) -> pd.Series:
    """
    This will generate values without any noise, just constant values according to 'docs/Heat production.md'.
    This serves as an alternative to using the 'coop_space_heating_produced' column of 'full_mock_energy_data.csv'.
    """
    max_prod = _get_grocery_store_max_prod(size_atemp_sqm)
    values = [_get_grocery_store_hourly_factor(timestamp) * max_prod for timestamp in datetimes]
    return pd.Series(values, index=datetimes)


def _get_bakery_hourly_factor(timestamp: datetime.datetime) -> float:
    """
    10 hours per day, as specified by BDAB ('docs/Heat production.md')
    """
    if 3 <= timestamp.hour < 13:
        return 1.0
    return 0.0


def _bakery_heat_production(datetimes: pd.DatetimeIndex) -> pd.Series:
    """
    This will generate values without any noise, just constant values according to 'docs/Heat production.md'.
    """
    values = [_get_grocery_store_hourly_factor(timestamp) * 300.0 for timestamp in datetimes]
    return pd.Series(values, index=datetimes)


def calculate_heat_production(agent, inputs_df: pd.DataFrame) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """
    Returns mock data of heat production, for heat producer agents.
    In the returned tuple, the first entry will be for low-tempered heat, and the second for high-tempered heat.
    """
    low_temp_heat = None
    high_temp_heat = None
    if agent['Profile'] == 'Grocery store':
        # We re-use the work done to emulate the Coop store, rather than use _grocery_store_heat_production, since
        # the latter doesn't take outdoor temperature into account.
        low_temp_heat = (inputs_df['coop_space_heating_produced']
                         - inputs_df['coop_space_heating_consumed']).clip(0.0)
        # Scaling here to fit BDAB's estimate (docs/Heat production.md)
        low_temp_heat = low_temp_heat * agent['Scale'] / 4.0
    elif agent['Profile'] == 'Bakery':
        high_temp_heat = _bakery_heat_production(inputs_df.index)
    else:
        raise ValueError('Unexpected HeatProducerAgent profile: {}'.format(agent['Profile']))
    return low_temp_heat, high_temp_heat
