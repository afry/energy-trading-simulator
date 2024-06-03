import datetime

import pandas as pd

from tradingplatformpoc.trading_platform_utils import should_use_summer_mode


def get_grocery_store_hourly_factor(timestamp: datetime.datetime) -> float:
    """
    Assuming opening hours 8-22 every day.
    See also https://doc.afdrift.se/pages/viewpage.action?pageId=46203534
    """
    if should_use_summer_mode(timestamp):
        if 8 <= timestamp.hour < 22:
            return 1.0
        else:
            return 0.75
    return 0.0


def get_grocery_store_max_prod(size_atemp_sqm: float) -> float:
    """
    Assuming that a size of 6000 sqm leads to a max production of 80 kW, scaling linearly.
    See also https://doc.afdrift.se/pages/viewpage.action?pageId=46203534
    """
    return (size_atemp_sqm / 6000.0) * 80.0


def grocery_store_heat_production(datetimes: pd.DatetimeIndex,
                                  size_atemp_sqm: float) -> pd.Series:
    """
    This will generate values without any noise, just constant values according to
    https://doc.afdrift.se/pages/viewpage.action?pageId=46203534.
    This serves as an alternative to using the 'coop_space_heating_produced' column of 'full_mock_energy_data.csv'.
    """
    max_prod = get_grocery_store_max_prod(size_atemp_sqm)
    values = [get_grocery_store_hourly_factor(timestamp) * max_prod for timestamp in datetimes]
    return pd.Series(values, index=datetimes)
