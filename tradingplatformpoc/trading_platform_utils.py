from datetime import datetime, timedelta
from typing import Any, Collection, Dict, List

import numpy as np

import pandas as pd

from tradingplatformpoc.bid import Resource

ALL_IMPLEMENTED_RESOURCES = [Resource.ELECTRICITY, Resource.HEATING]
ALL_IMPLEMENTED_RESOURCES_STR = [res.name for res in ALL_IMPLEMENTED_RESOURCES]
ALL_AGENT_TYPES = ["BuildingAgent", "PVAgent", "StorageAgent", "GridAgent", "GroceryStoreAgent"]
HEAT_TRANSFER_LOSS_PER_SIDE = 1 - np.sqrt(0.95)  # Square root since it is added both to the BUY and the SELL side


def minus_n_hours(t1: datetime, n_hours: int):
    new_time = t1 - timedelta(hours=n_hours)
    return new_time


def hourly_datetime_array_between(from_dt: datetime, to_dt: datetime):
    delta = to_dt - from_dt
    delta_hours = int(delta.days * 24 + delta.seconds / 3600)
    to_return = [from_dt]
    for i in range(delta_hours):
        to_return.append(from_dt + timedelta(hours=i + 1))
    return to_return


def get_intersection(collection1: Collection, collection2: Collection) -> List:
    """Returns a list of items that are present in both collection1 and collection2. Ordered the same as collection1."""
    temp = set(collection2)
    return [value for value in collection1 if value in temp]


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


def nan_helper(y):
    """Helper to handle indices and logical indices of NaNs.

    Input:
        - y, 1d numpy array with possible NaNs
    Output:
        - nans, logical indices of NaNs
        - index, a function, with signature indices= index(logical_indices),
          to convert logical indices of NaNs to 'equivalent' indices
    Example:
        >>> # linear interpolation of NaNs
        >>> y = np.array([1.0, np.nan, 2.0])
        >>> nans, x= nan_helper(y)
        >>> y[nans]= np.interp(x(nans), x(~nans), y[~nans])
    """

    return np.isnan(y), lambda z: z.nonzero()[0]


def get_if_exists_else(some_dict: Dict[str, Any], key: str, default_value: Any) -> Any:
    """If some_dict has a 'key' attribute, use that, else use the default value."""
    return some_dict[key] if key in some_dict else default_value


def add_to_nested_dict(nested_dict: dict, key1, key2, value):
    if key1 in nested_dict:
        nested_dict[key1][key2] = value
    else:
        nested_dict[key1] = {key2: value}
