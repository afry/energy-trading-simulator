from typing import List, Union

import pandas as pd

import polars as pl


def scale_energy_consumption(unscaled_simulated_values_kwh: pl.LazyFrame, m2: float,
                             kwh_per_year_per_m2: float, n_rows: int) -> pl.LazyFrame:
    if n_rows > 8760:
        # unscaled_simulated_values may contain more than 1 year, so to scale, compare the sum of the first 8766 hours
        # i.e. 365.25 days, with the wanted yearly sum.
        wanted_yearly_sum = m2 * kwh_per_year_per_m2
        return unscaled_simulated_values_kwh. \
            with_row_count(). \
            select([pl.col('datetime'),
                    pl.col('value') * wanted_yearly_sum / pl.col('value').where(pl.col('row_nr') < 8766).sum()])
    else:
        raise RuntimeError("Less than a year's worth of data!")


def add_datetime_value_frames(dfs: List[Union[pl.DataFrame, pl.LazyFrame]]) -> Union[pl.DataFrame, pl.LazyFrame]:
    """Works on both DataFrame and LazyFrame"""
    if len(dfs) == 1:
        return dfs[0]
    else:
        base_df = dfs[0]
        for i in range(1, len(dfs)):
            base_df = base_df.join(dfs[i], on='datetime'). \
                select([pl.col('datetime'), (pl.col('value') + pl.col('value_right')).alias('value')])
        return base_df


def is_major_holiday_sweden(timestamp: pd.Timestamp) -> bool:
    swedish_time = timestamp.tz_convert("Europe/Stockholm")
    month_of_year = swedish_time.month
    day_of_month = swedish_time.day
    # Major holidays will naturally have a big impact on household electricity usage patterns, with people not working
    # etc. Included here are: Christmas eve, Christmas day, Boxing day, New years day, epiphany, 1 may, national day.
    # Some moveable ones not included (Easter etc)
    return ((month_of_year == 12) & (day_of_month == 24)) | \
           ((month_of_year == 12) & (day_of_month == 25)) | \
           ((month_of_year == 12) & (day_of_month == 26)) | \
           ((month_of_year == 1) & (day_of_month == 1)) | \
           ((month_of_year == 1) & (day_of_month == 6)) | \
           ((month_of_year == 5) & (day_of_month == 1)) | \
           ((month_of_year == 6) & (day_of_month == 6))


def is_day_before_major_holiday_sweden(timestamp: pd.Timestamp) -> bool:
    swedish_time = timestamp.tz_convert("Europe/Stockholm")
    month_of_year = swedish_time.month
    day_of_month = swedish_time.day
    # Major holidays will naturally have a big impact on household electricity usage patterns, with people not working
    # etc. Included here are:
    # Day before christmas eve, New years eve, day before epiphany, Valborg, day before national day.
    return ((month_of_year == 12) & (day_of_month == 23)) | \
           ((month_of_year == 12) & (day_of_month == 31)) | \
           ((month_of_year == 1) & (day_of_month == 5)) | \
           ((month_of_year == 4) & (day_of_month == 30)) | \
           ((month_of_year == 6) & (day_of_month == 5))
