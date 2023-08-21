import numpy as np

import pandas as pd

import polars as pl

from pkg_resources import resource_filename

# This file contains functions used for reading and preprocessing data from files.


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
    return price_data


def read_energy_data(data_path: str = "tradingplatformpoc.data",
                     energy_data_file: str = "full_mock_energy_data.csv") -> pd.DataFrame:
    energy_data_csv_path = resource_filename(data_path, energy_data_file)
    energy_data = pd.read_csv(energy_data_csv_path, index_col=0)
    energy_data.index = pd.to_datetime(energy_data.index, utc=True)
    return energy_data['tornet_electricity_consumed_household_kwh'], \
        energy_data['coop_electricity_consumed_cooling_kwh'] + \
        energy_data['coop_electricity_consumed_other_kwh'], \
        energy_data['tornet_energy_consumed_heat_kwh'], \
        np.maximum(energy_data['coop_net_heat_consumed'], 0)  # Indications are Coop has no excess heat so setting to 0


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

def create_inputs_df_for_mock_data_generation(
        df_temp: pd.DataFrame = read_temperature_data(),
        df_irrd: pd.DataFrame = read_irradiation_data(),
        df_heat: pd.DataFrame = read_heating_data()) -> pl.DataFrame:
    """
    Create pl.DataFrames with certain columns that are needed to predict from the household electricity linear model.
    Will start reading CSVs as pd.DataFrames, since pandas is better at handling time zones, and then convert to polars.
    @param df_temp: Dataframe with datetime-stamps and temperature readings, in degrees C.
    @param df_irrd: Dataframe with datetime-stamps and solar irradiance readings, in W/m2.
    @param df_heat: Dataframe with datetime-stamps and heating energy readings, in kW.
    @return: A pl.DataFrames containing date/time-related columns, as well as outdoor temperature readings and
             heating energy demand data from Vetelangden, which will be used to simulate electricity and heat demands,
             and also irradiation data, which is used to estimate PV production.
    """
    df_inputs = df_temp.merge(df_irrd)

    # In case there are any missing values
    df_inputs[['temperature', 'irradiation']] = df_inputs[['temperature', 'irradiation']].interpolate(method='linear')

    df_inputs['hour_of_day'] = df_inputs['datetime'].dt.hour + 1
    df_inputs['day_of_week'] = df_inputs['datetime'].dt.dayofweek + 1
    df_inputs['day_of_month'] = df_inputs['datetime'].dt.day
    df_inputs['month_of_year'] = df_inputs['datetime'].dt.month
    df_inputs['major_holiday'] = df_inputs['datetime'].apply(lambda dt: is_major_holiday_sweden(dt))
    df_inputs['pre_major_holiday'] = df_inputs['datetime'].apply(lambda dt: is_day_before_major_holiday_sweden(dt))

    df_inputs = df_inputs.merge(df_heat)

    return pl.from_pandas(df_inputs)


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
