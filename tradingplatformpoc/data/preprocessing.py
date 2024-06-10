import datetime
import functools
import logging

import numpy as np

import pandas as pd

from pkg_resources import resource_filename


# This file contains functions used for reading and preprocessing data from files.

logger = logging.getLogger(__name__)


# Read CSVs
# ----------------------------------------------------------------------------------------------------------------------


def read_irradiation_data(data_path: str = "tradingplatformpoc.data",
                          irradiation_file: str = "varberg_irradiation_W_m2_h.csv"
                          ) -> pd.DataFrame:
    """Return solar irradiation, according to SMHI, in Watt per square meter"""
    irradiation_csv_path = resource_filename(data_path, irradiation_file)
    irradiation_data = pd.read_csv(irradiation_csv_path)
    # This irradiation data is in UTC, so we don't need to convert it.
    irradiation_data['datetime'] = pd.to_datetime(irradiation_data['datetime'], utc=True)
    return irradiation_data


def read_nordpool_data(data_path: str = "tradingplatformpoc.data") -> pd.DataFrame:
    price_dfs = []
    for external_price_file, utc in zip(["nordpool_area_grid_el_price.csv", "nordpool_2022-2024.csv"], [True, False]):
        external_price_csv_path = resource_filename(data_path, external_price_file)
        price_data = pd.read_csv(external_price_csv_path, index_col=0)
        price_data = price_data.squeeze()
        if price_data.mean() > 100:
            # convert price from SEK per MWh to SEK per kWh
            price_data = price_data / 1000
        price_data.index = pd.to_datetime(price_data.index, utc=utc)
        if not utc:
            price_data.index = price_data.index.tz_localize('CET', nonexistent='NaT', ambiguous='infer')
            # There will be some NaT with NA prices, remove those:
            price_data = price_data.dropna()
        price_df = pd.DataFrame(price_data).reset_index()
        price_df = price_df.rename(columns={'dayahead_SE3_el_price': 'dayahead_se3_el_price'})
        price_dfs.append(price_df)
    return pd.concat(price_dfs)


def read_energy_data(data_path: str = "tradingplatformpoc.data",
                     energy_data_file: str = "full_mock_energy_data.csv") -> pd.DataFrame:
    # "full_mock_energy_data.csv" is generated in data-exploration, compare_coop_and_tornet.ipynb
    energy_data_csv_path = resource_filename(data_path, energy_data_file)
    energy_data = pd.read_csv(energy_data_csv_path, index_col=0)
    energy_data.index = pd.to_datetime(energy_data.index, utc=True)
    energy_data['coop_electricity_consumed'] = energy_data['coop_electricity_consumed_cooling_kwh'] \
        + energy_data['coop_electricity_consumed_other_kwh']
    energy_data['coop_hot_tap_water_consumed'] = energy_data['coop_hw_consumed_kwh']
    # Excess heat when coop_net_space_heat_consumed is negative:
    energy_data['coop_space_heating_produced'] = -np.minimum(energy_data['coop_net_space_heat_consumed'], 0)
    energy_data['coop_space_heating_consumed'] = np.maximum(energy_data['coop_net_space_heat_consumed'], 0)
    return energy_data[['coop_electricity_consumed', 'coop_hot_tap_water_consumed',
                        'coop_space_heating_consumed', 'coop_space_heating_produced']].reset_index()


def read_temperature_data(data_path: str = "tradingplatformpoc.data",
                          energy_data_file: str = 'temperature_vetelangden.csv') -> pd.DataFrame:
    temperature_csv_path = resource_filename(data_path, energy_data_file)
    df_temp = pd.read_csv(temperature_csv_path, names=['datetime', 'temperature'],
                          delimiter=';', header=0)
    df_temp['datetime'] = pd.to_datetime(df_temp['datetime'])
    # The input is in local time, with NA for the times that "don't exist" due to daylight savings time
    df_temp['datetime'] = df_temp['datetime'].dt.tz_localize('Europe/Stockholm', nonexistent='NaT', ambiguous='NaT')
    # Now, remove the rows where datetime is NaT (the values there are NA anyway)
    df_temp = df_temp.loc[~df_temp['datetime'].isnull()]
    # Finally, convert to UTC
    df_temp['datetime'] = df_temp['datetime'].dt.tz_convert('UTC')
    return df_temp


def read_heating_data(data_path: str = "tradingplatformpoc.data",
                      energy_data_file: str = 'vetelangden_slim.csv') -> pd.DataFrame:
    heating_csv_path = resource_filename(data_path, energy_data_file)
    df_heat = pd.read_csv(heating_csv_path, names=['datetime', 'rad_energy', 'hw_energy'], header=0)
    df_heat['datetime'] = pd.to_datetime(df_heat['datetime'])
    # The input is in local time, a bit unclear about times that "don't exist" when DST starts, or "exist twice" when
    # DST ends - will remove such rows, they have some NAs and stuff anyway
    df_heat['datetime'] = df_heat['datetime'].dt.tz_localize('Europe/Stockholm', nonexistent='NaT', ambiguous='NaT')
    df_heat = df_heat.loc[~df_heat['datetime'].isnull()]
    # Finally, convert to UTC
    df_heat['datetime'] = df_heat['datetime'].dt.tz_convert('UTC')
    return df_heat


def read_office_data(data_path: str = 'tradingplatformpoc.data',
                     office_data_file: str = 'office_hourly.csv') -> pd.DataFrame:
    csv_path = resource_filename(data_path, office_data_file)
    hourly_data = pd.read_csv(csv_path, sep=';', header=None, skiprows=4,
                              names=['datetime', 'office_cooling', 'office_space_heating'])
    # This file is for 2019, even though it says 2021. Our other data is 2019-02 - 2020-01, so we'll take 2019-01 from
    # this data and move it to 2020-01.
    hourly_data['datetime'] = pd.to_datetime(hourly_data['datetime'].astype(str).str.
                                             replace('2021-01', '2020-01').str.
                                             replace('2021-', '2019-'))
    # Do the timezone thing as above
    hourly_data['datetime'] = hourly_data['datetime'].dt. \
        tz_localize('Europe/Stockholm', nonexistent='NaT', ambiguous='NaT')
    hourly_data = hourly_data.loc[~hourly_data['datetime'].isnull()]
    # Finally, convert to UTC
    hourly_data['datetime'] = hourly_data['datetime'].dt.tz_convert('UTC')
    # One duplicate, when going from DST, remove it:
    hourly_data = hourly_data.groupby('datetime').mean().reset_index()

    # Missing one entry at the end:
    # Find the last row
    last_row = hourly_data.iloc[-1]
    # Increment datetime by 1 hour
    new_datetime = last_row['datetime'] + datetime.timedelta(hours=1)
    # Create a new row with datetime increased by 1 hour and other values copied from the last row
    new_row = last_row.copy()
    new_row['datetime'] = new_datetime
    # Append the new row to the DataFrame
    hourly_data = pd.concat([hourly_data, pd.DataFrame(new_row).transpose()], ignore_index=True)
    hourly_data['office_cooling'] = hourly_data['office_cooling'].astype(float)
    hourly_data['office_space_heating'] = hourly_data['office_space_heating'].astype(float)

    # Remove first row (2019-01-31 23:00)
    hourly_data = hourly_data.iloc[1:]

    return hourly_data


# Preprocess data
# ----------------------------------------------------------------------------------------------------------------------

def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Interpolate values for missing datetimes in dataframe range.
    The input df must have a column named 'datetime'.
    """
    df = df.set_index('datetime')
    datetime_range = pd.date_range(start=df.index.min(), end=df.index.max(),
                                   freq="1h", tz='utc')
    missing_datetimes = datetime_range.difference(df.index)
    if len(missing_datetimes) > 0:
        logger.info("{} missing datetime/s in data. Will fill using linear interpolation."
                    .format(len(missing_datetimes)))
        df = df.reindex(datetime_range)
        df = df.interpolate('linear')
    return df


def read_and_process_input_data() -> pd.DataFrame:
    """
    Create input dataframe.
    """
    dfs = [read_irradiation_data(),
           read_temperature_data(),
           read_heating_data(),
           read_energy_data(),
           read_office_data()]
    dfs_cleaned = [clean(df) for df in dfs]
    df_merged = functools.reduce(lambda left, right: left.join(right, on='datetime', how='inner'), dfs_cleaned)
    return df_merged.reset_index()
