import functools
import logging

import numpy as np

import pandas as pd

from pkg_resources import resource_filename


# This file contains functions used for reading and preprocessing data from files.

logger = logging.getLogger(__name__)


# Read CSVs
# ----------------------------------------------------------------------------------------------------------------------

def read_electricitymap_data(data_path: str = "tradingplatformpoc.data",
                             electricitymap_file: str = "electricity_co2equivalents_year2019.csv"
                             ) -> pd.Series:
    """
    Reads the electricity map CSV file. Returns a pd.Series with the marginal carbon intensity.
    """
    electricitymap_csv_path = resource_filename(data_path, electricitymap_file)

    em_data = pd.read_csv(electricitymap_csv_path, delimiter=';')
    em_data.index = pd.to_datetime(em_data['timestamp'], unit='s')
    # The input is in local time, with NA for the times that "don't exist" due to daylight savings time
    em_data = em_data.tz_localize('Europe/Stockholm', nonexistent='NaT', ambiguous='NaT')
    # Now, remove the rows where datetime is NaT (the values there are NA anyway)
    em_data = em_data.loc[~em_data.index.isnull()]
    # Finally, convert to UTC
    em_data = em_data.tz_convert('UTC')
    return em_data['marginal_carbon_intensity_avg']


def read_irradiation_data(data_path: str = "tradingplatformpoc.data",
                          irradiation_file: str = "varberg_irradiation_W_m2_h.csv"
                          ) -> pd.DataFrame:
    """Return solar irradiation, according to SMHI, in Watt per square meter"""
    irradiation_csv_path = resource_filename(data_path, irradiation_file)
    irradiation_data = pd.read_csv(irradiation_csv_path)
    # This irradiation data is in UTC, so we don't need to convert it.
    irradiation_data['datetime'] = pd.to_datetime(irradiation_data['datetime'], utc=True)
    return irradiation_data


def read_nordpool_data(data_path: str = "tradingplatformpoc.data",
                       external_price_file: str = "nordpool_area_grid_el_price.csv"
                       ) -> pd.Series:
    external_price_csv_path = resource_filename(data_path, external_price_file)
    price_data = pd.read_csv(external_price_csv_path, index_col=0)
    price_data = price_data.squeeze()
    if price_data.mean() > 100:
        # convert price from SEK per MWh to SEK per kWh
        price_data = price_data / 1000
    price_data.index = pd.to_datetime(price_data.index, utc=True)
    price_df = pd.DataFrame(price_data).reset_index()
    price_df = price_df.rename(columns={'dayahead_SE3_el_price': 'dayahead_se3_el_price'})
    return price_df


def read_energy_data(data_path: str = "tradingplatformpoc.data",
                     energy_data_file: str = "full_mock_energy_data.csv") -> pd.DataFrame:
    energy_data_csv_path = resource_filename(data_path, energy_data_file)
    energy_data = pd.read_csv(energy_data_csv_path, index_col=0)
    energy_data.index = pd.to_datetime(energy_data.index, utc=True)
    energy_data['coop_electricity_consumed'] = energy_data['coop_electricity_consumed_cooling_kwh'] \
        + energy_data['coop_electricity_consumed_other_kwh']
    # Indications are Coop has no excess heat so setting to 0
    energy_data['coop_heating_consumed'] = np.maximum(energy_data['coop_net_heat_consumed'], 0)
    return energy_data[['coop_electricity_consumed', 'coop_heating_consumed']].reset_index()


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


# Preprocess data
# ----------------------------------------------------------------------------------------------------------------------

def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Interpolate values for missing datetimes in dataframe range.
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


def read_and_process_input_data():
    """
    Create input dataframe.
    """
    dfs = [read_irradiation_data(), read_temperature_data(), read_heating_data(), read_energy_data()]
    dfs_cleaned = [clean(df) for df in dfs]
    df_merged = functools.reduce(lambda left, right: left.join(right, on='datetime', how='inner'), dfs_cleaned)
    return df_merged.reset_index()
