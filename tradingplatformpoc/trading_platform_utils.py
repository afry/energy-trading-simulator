import logging
import platform
from datetime import datetime, timedelta
from typing import Any, Collection, Dict, List

import numpy as np

import pandas as pd

import pyomo.environ as pyo
from pyomo.opt import OptSolver

from tradingplatformpoc.market.trade import Resource
from tradingplatformpoc.price.iprice import IPrice
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


def add_to_twice_nested_dict(twice_nested_dict: Dict[Any, Dict[Any, dict]], key1, key2, key3, value):
    """
    Emulates add_to_nested_dict but with one more level
    """
    if key1 in twice_nested_dict:
        add_to_nested_dict(twice_nested_dict[key1], key2, key3, value)
    else:
        twice_nested_dict[key1] = {key2: {key3: value}}


def add_all_to_nested_dict(nested_dict: Dict[Any, dict], other_nested_dict: Dict[Any, dict]):
    """
    Will add all data from other_nested_dict into nested_dict. If there are key pairs that exist in both, the values
    in other_nested_dict will overwrite those in nested_dict.
    """
    for (k1, subdict) in other_nested_dict.items():
        for (k2, v) in subdict.items():
            add_to_nested_dict(nested_dict, k1, k2, v)


def add_all_to_twice_nested_dict(first_dict: Dict[Any, Dict[Any, dict]], second_dict: Dict[Any, Dict[Any, dict]]):
    """
    Will add all data from first_dict into second_dict. If there are key pairs that exist in both, the values
    in second_dict will overwrite those in first_dict.
    """
    for (k1, subdict1) in second_dict.items():
        for (k2, subdict2) in subdict1.items():
            for (k3, v) in subdict2.items():
                add_to_twice_nested_dict(first_dict, k1, k2, k3, v)


def get_glpk_solver() -> OptSolver:
    if platform.system() == 'Linux':
        logger.info('Linux system')
        return pyo.SolverFactory('glpk')
    else:
        logger.info('Not a linux system, using GLPK_PATH')
        return pyo.SolverFactory('glpk', executable=settings.GLPK_PATH)


def get_external_prices(pricing: IPrice, job_id: str,
                        trading_periods: Collection[datetime], block_agent_ids: List[str],
                        local_market_enabled: bool) -> List[Dict[str, Any]]:
    prices_by_dt_list: List[Dict[str, Any]] = []
    agent_ids = [None] if local_market_enabled else block_agent_ids
    for dt in trading_periods:
        for agent_id in agent_ids:  # type: ignore
            prices_by_dt_list.append({
                'job_id': job_id,
                'period': dt,
                'agent': agent_id,
                'exact_retail_price': pricing.get_exact_retail_price(dt, include_tax=True, agent=agent_id),
                'exact_wholesale_price': pricing.get_exact_wholesale_price(dt, agent=agent_id),
                'estimated_retail_price': pricing.get_retail_price_estimate(dt, agent_id),
                # Estimated wholesale price is known at the time, in the current implementation
                'estimated_wholesale_price': pricing.get_exact_wholesale_price(dt, agent=agent_id)
            })
    return prices_by_dt_list


def get_final_storage_level(trading_horizon: int,
                            storage_by_period_and_agent: Dict[str, Dict[datetime, float]],
                            horizon_start: datetime) -> Dict[str, float]:
    """For each agent, return the value for the final period in the input dict."""
    return {agent: sub_dict[horizon_start + timedelta(hours=trading_horizon - 1)]
            for agent, sub_dict in storage_by_period_and_agent.items()}


def sum_nested_dict_values(levels_dict: Dict[Any, Dict[Any, float]]) -> float:
    return sum(sum(subdict.values()) for subdict in levels_dict.values())


def water_volume_to_energy(volume_m3: float, temperature_c: float = 65) -> float:
    """Returns energy in kilowatt-hours."""
    # Specific heat of water is 4182 J/(kg C)
    # Density of water is 998 kg/m3
    return temperature_c * volume_m3 * 4182 * 998 / 3600000


def energy_to_water_volume(energy_kwh: float, temperature_c: float = 65) -> float:
    """Returns volume in cubic metres."""
    # Specific heat of water is 4182 J/(kg C)
    # Density of water is 998 kg/m3
    return energy_kwh / (temperature_c * 4182 * 998 / 3600000)


def weekdays_diff(from_year: int, to_year: int) -> int:
    jan1_weekday_1 = pd.Timestamp(str(from_year) + "-01-01").dayofweek
    jan1_weekday_2 = pd.Timestamp(str(to_year) + "-01-01").dayofweek
    return (jan1_weekday_1 - jan1_weekday_2) % 7
