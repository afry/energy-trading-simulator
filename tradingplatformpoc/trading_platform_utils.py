import logging
import platform
from datetime import datetime, timedelta
from typing import Any, Collection, Dict, List

import numpy as np

import pandas as pd

import pyomo.environ as pyo
from pyomo.opt import OptSolver

from tradingplatformpoc.market.trade import Resource
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.settings import settings

ALLOWED_GRID_AGENT_RESOURCES = [Resource.ELECTRICITY, Resource.HIGH_TEMP_HEAT]
ALLOWED_GRID_AGENT_RESOURCES_STR = [res.name for res in ALLOWED_GRID_AGENT_RESOURCES]
ALL_AGENT_TYPES = ["BlockAgent", "GridAgent", "GroceryStoreAgent"]

logger = logging.getLogger(__name__)


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


def add_to_nested_dict(nested_dict: Dict[Any, dict], key1, key2, value):
    """
    Will add value to nested_dict, using key1 and then key2.
    If nested_dict already has a value for these keys, it will be overwritten.
    If nested_dict[key1] is empty, a new dict will be assigned to it, with the (key2: value) pair.
    """
    if key1 in nested_dict:
        nested_dict[key1][key2] = value
    else:
        nested_dict[key1] = {key2: value}


def add_all_to_nested_dict(nested_dict: Dict[Any, dict], other_nested_dict: Dict[Any, dict]):
    """
    Will add all data from other_nested_dict into nested_dict. If there are key pairs that exist in both, the values
    in other_nested_dict will overwrite those in nested_dict.
    """
    for (k1, subdict) in other_nested_dict.items():
        for (k2, v) in subdict.items():
            add_to_nested_dict(nested_dict, k1, k2, v)


def get_glpk_solver() -> OptSolver:
    if platform.system() == 'Linux':
        logger.info('Linux system')
        return pyo.SolverFactory('glpk')
    else:
        logger.info('Not a linux system, using GLPK_PATH')
        return pyo.SolverFactory('glpk', executable=settings.GLPK_PATH)


def get_external_heating_prices(heat_pricing: HeatingPrice, job_id: str,
                                trading_periods: Collection[datetime]) -> List[Dict[str, Any]]:
    heating_price_by_ym_list: List[Dict[str, Any]] = []
    for (year, month) in set([(dt.year, dt.month) for dt in trading_periods]):
        first_day_of_month = datetime(year, month, 1)  # Which day it is doesn't matter
        heating_price_by_ym_list.append({
            'job_id': job_id,
            'year': year,
            'month': month,
            'exact_retail_price': heat_pricing.get_exact_retail_price(first_day_of_month, include_tax=True),
            'exact_wholesale_price': heat_pricing.get_exact_wholesale_price(first_day_of_month),
            'estimated_retail_price': heat_pricing.get_estimated_retail_price(first_day_of_month, include_tax=True),
            'estimated_wholesale_price': heat_pricing.get_estimated_wholesale_price(first_day_of_month)})
    return heating_price_by_ym_list
