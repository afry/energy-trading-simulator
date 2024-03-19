import datetime
from typing import List, Union

import pandas as pd

import polars as pl

import pytz

SWEDEN_TIMEZONE = pytz.timezone("Europe/Stockholm")


def scale_energy_consumption(unscaled_simulated_values_kwh: pl.LazyFrame, m2: float,
                             kwh_per_year_per_m2: float, n_rows: int) -> pl.LazyFrame:
    if n_rows >= 8760:
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


def is_major_holiday_sweden(dt: datetime.datetime) -> bool:
    swedish_time = dt.astimezone(SWEDEN_TIMEZONE)
    month_of_year = swedish_time.month
    day_of_month = swedish_time.day
    # Major holidays will naturally have a big impact on household electricity usage patterns, with people not working
    # etc. Included here are: Christmas Eve, Christmas day, Boxing day, New years day, epiphany, 1 may, national day.
    # Some movable ones not included (Easter etc.)
    return ((month_of_year == 12) & (day_of_month == 24)) | \
           ((month_of_year == 12) & (day_of_month == 25)) | \
           ((month_of_year == 12) & (day_of_month == 26)) | \
           ((month_of_year == 1) & (day_of_month == 1)) | \
           ((month_of_year == 1) & (day_of_month == 6)) | \
           ((month_of_year == 5) & (day_of_month == 1)) | \
           ((month_of_year == 6) & (day_of_month == 6))


def is_day_before_major_holiday_sweden(dt: datetime.datetime) -> bool:
    swedish_time = dt.astimezone(SWEDEN_TIMEZONE)
    month_of_year = swedish_time.month
    day_of_month = swedish_time.day
    # Major holidays will naturally have a big impact on household electricity usage patterns, with people not working
    # etc. Included here are:
    # Day before Christmas Eve, New years eve, day before epiphany, Valborg, day before national day.
    return ((month_of_year == 12) & (day_of_month == 23)) | \
           ((month_of_year == 12) & (day_of_month == 31)) | \
           ((month_of_year == 1) & (day_of_month == 5)) | \
           ((month_of_year == 4) & (day_of_month == 30)) | \
           ((month_of_year == 6) & (day_of_month == 5))


def extract_datetime_features_from_inputs_df(df_inputs: pd.DataFrame) -> pl.DataFrame:
    """
    Create pl.DataFrames with certain columns that are needed to predict from the household electricity linear model.
    Will start reading CSVs as pd.DataFrames, since pandas is better at handling time zones, and then convert to polars.
    @param df_inputs: Dataframe with datetime-stamps and temperature readings, in degrees C,
                      solar irradiance readings, in W/m2 and heating energy readings, in kW.
    @return: A pl.DataFrames containing date/time-related columns, as well as outdoor temperature readings and
             heating energy demand data from Vetelangden, which will be used to simulate electricity and heat demands,
             and also irradiation data, which is used to estimate PV production.
    """
    df_inputs['hour_of_day'] = df_inputs['datetime'].dt.hour + 1
    df_inputs['day_of_week'] = df_inputs['datetime'].dt.dayofweek + 1
    df_inputs['day_of_month'] = df_inputs['datetime'].dt.day
    df_inputs['month_of_year'] = df_inputs['datetime'].dt.month
    df_inputs['major_holiday'] = df_inputs['datetime']. \
        apply(lambda dt: is_major_holiday_sweden(dt.to_pydatetime()))
    df_inputs['pre_major_holiday'] = df_inputs['datetime']. \
        apply(lambda dt: is_day_before_major_holiday_sweden(dt.to_pydatetime()))

    return pl.from_pandas(df_inputs)


def constants(df_inputs: pl.LazyFrame, val: float) -> pl.LazyFrame:
    return df_inputs.select([pl.col('datetime'), pl.lit(val).alias('value')])
