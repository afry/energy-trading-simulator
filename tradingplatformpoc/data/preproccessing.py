import numpy as np

import pandas as pd

from pkg_resources import resource_filename


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
                          ) -> pd.Series:
    irradiation_csv_path = resource_filename(data_path, irradiation_file)
    """Return solar irradiation, according to SMHI, in Watt per square meter"""
    irradiation_data = pd.read_csv(irradiation_csv_path, index_col=0)
    irradiation_series = irradiation_data['irradiation']
    irradiation_series.index = pd.to_datetime(irradiation_series.index, utc=True)
    return irradiation_series


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
                     energy_data_file: str = "full_mock_energy_data.csv"):
    energy_data_csv_path = resource_filename(data_path, energy_data_file)
    energy_data = pd.read_csv(energy_data_csv_path, index_col=0)
    energy_data.index = pd.to_datetime(energy_data.index, utc=True)
    return energy_data['tornet_electricity_consumed_household_kwh'], \
        energy_data['coop_electricity_consumed_cooling_kwh'] + \
        energy_data['coop_electricity_consumed_other_kwh'], \
        energy_data['tornet_energy_consumed_heat_kwh'], \
        np.maximum(energy_data['coop_net_heat_consumed'], 0)  # Indications are Coop has no excess heat so setting to 0
