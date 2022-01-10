from datetime import datetime, timedelta

import pandas as pd


def minus_n_hours(t1: datetime, n_hours: int):
    new_time = t1 - timedelta(hours=n_hours)
    return new_time


def datetime_array(from_dt: datetime, to_dt: datetime):
    delta = to_dt - from_dt
    delta_hours = int(delta.days * 24 + delta.seconds / 3600)
    to_return = [from_dt]
    for i in range(delta_hours):
        to_return.append(from_dt + timedelta(hours=i + 1))
    return to_return


def datetime_indexed_value_series(datetimes, values):
    ser = pd.Series(values, index=datetimes)
    return ser


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
