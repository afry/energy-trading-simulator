from datetime import datetime, timedelta
from typing import Any, Collection, Dict, List

import pandas as pd

from tradingplatformpoc.bid import Resource


ALL_IMPLEMENTED_RESOURCES = [Resource.ELECTRICITY, Resource.HEATING]


def minus_n_hours(t1: datetime, n_hours: int):
    new_time = t1 - timedelta(hours=n_hours)
    return new_time


def datetime_array_between(from_dt: datetime, to_dt: datetime):
    delta = to_dt - from_dt
    delta_hours = int(delta.days * 24 + delta.seconds / 3600)
    to_return = [from_dt]
    for i in range(delta_hours):
        to_return.append(from_dt + timedelta(hours=i + 1))
    return to_return


def get_intersection(list1, list2):
    """Returns a list of items that are present in both list1 and list2. Ordered the same as list1."""
    return [item for item in list1 if item in list2]


def calculate_solar_prod(irradiation_data: pd.Series, pv_sqm: float, pv_efficiency: float):
    """
    Calculates the solar energy production from some solar panels, given irradiation, total size of solar panels, and
    their efficiency.

    Parameters
    ----------
    irradiation_data : pd.Series
        Irradiation data per datetime, in W/m2
    pv_sqm : float
        Total square meterage of solar panels
    pv_efficiency : float
        Efficiency of solar panels

    Returns
    -------
    pd.Series
        The solar energy production in kWh
    """
    return irradiation_data * pv_sqm * pv_efficiency / 1000


def add_numeric_dicts(dict1: Dict[Any, float], dict2: Dict[Any, float]) -> Dict[Any, float]:
    """
    Add values for keys that exist in both, keep all keys.
    This could have been done smoothly with collections.Counter, but that doesn't include keys for which the value is 0,
    which we want.
    """
    combined_dict = dict1.copy()
    for k, v in dict2.items():
        if k in combined_dict:
            combined_dict[k] = combined_dict[k] + v
        else:
            combined_dict[k] = v
    return combined_dict


def flatten_collection(collection_of_lists: Collection[Collection[Any]]) -> List[Any]:
    return [bid for sublist in collection_of_lists for bid in sublist]
