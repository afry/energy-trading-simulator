import pandas as pd
from pkg_resources import resource_filename

from tradingplatformpoc.trading_platform_utils import minus_n_hours, calculate_solar_prod


class DataStore:
    nordpool_data: pd.Series
    tornet_park_pv_prod: pd.Series
    coop_pv_prod: pd.Series  # Rooftop PV production

    def __init__(self, config_area_info, nordpool_data, irradiation_data):
        self.pv_efficiency = config_area_info["PVEfficiency"]
        self.store_pv_area = config_area_info["StorePVArea"]
        self.park_pv_area = config_area_info["ParkPVArea"]

        self.nordpool_data = nordpool_data
        self.coop_pv_prod = calculate_solar_prod(irradiation_data, self.store_pv_area, self.pv_efficiency)
        self.tornet_park_pv_prod = calculate_solar_prod(irradiation_data, self.park_pv_area, self.pv_efficiency)

    @staticmethod
    def from_csv_files(config_area_info,
                       external_price_csv_path=resource_filename("tradingplatformpoc.data",
                                                                 "nordpool_area_grid_el_price.csv"),
                       irradiation_csv_path=resource_filename("tradingplatformpoc.data",
                                                              "varberg_irradiation_W_m2_h.csv")):
        return DataStore(config_area_info,
                         read_nordpool_data(external_price_csv_path),
                         read_solar_irradiation(irradiation_csv_path))

    def get_nordpool_price_for_period(self, period):
        return self.nordpool_data.loc[period]

    def get_retail_price(self, period):
        """Returns the price at which the external grid operator is willing to sell electricity, in SEK/kWh"""
        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        return self.get_nordpool_price_for_period(period) + 0.48

    def get_wholesale_price(self, period):
        """Returns the price at which the external grid operator is willing to buy electricity, in SEK/kWh"""
        # Per https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        return self.get_nordpool_price_for_period(period) + 0.05

    def get_nordpool_data_datetimes(self):
        return self.nordpool_data.index.tolist()

    def get_nordpool_prices_last_n_hours_dict(self, period, go_back_n_hours):
        nordpool_prices_last_n_hours = {}
        for i in range(go_back_n_hours):
            t = minus_n_hours(period, i + 1)
            nordpool_prices_last_n_hours[t] = self.get_nordpool_price_for_period(t)
        return nordpool_prices_last_n_hours


def read_energy_data(energy_csv_path: str):
    energy_data = pd.read_csv(energy_csv_path, index_col=0)
    energy_data.index = pd.to_datetime(energy_data.index)
    return energy_data['tornet_electricity_consumed_household_kwh'], \
        energy_data['coop_electricity_consumed_cooling_kwh'] + \
        energy_data['coop_electricity_consumed_other_kwh'], \
        energy_data['tornet_energy_consumed_heat_kwh'], \
        energy_data['coop_net_heat_consumed']


def read_school_energy_consumption_csv(csv_path: str):
    """
    Reads a CSV file with electricity consumption data for a school.
    Taken from https://www.kaggle.com/nwheeler443/ai-day-level-1
    This probably includes electricity used for heating, but will overlook this potential flaw for now.
    @param csv_path: String specifying the path of the CSV file
    @return pd.Series
    """
    energy_data = pd.read_csv(csv_path)
    energy_data = pd.melt(energy_data, id_vars=['Reading Date', 'One Day Total kWh', 'Status', 'Substitute Date'],
                          var_name='Time', value_name="Energy")
    energy_data['Timestamp'] = pd.to_datetime(energy_data['Reading Date'] + " " +
                                              energy_data['Time'], format='%Y-%m-%d %H:%M')
    energy_data = energy_data.sort_values(by=['Timestamp'])
    energy_data = energy_data.set_index('Timestamp')
    energy_data = energy_data['Energy']
    energy_data = energy_data.resample('1H').sum()  # Half-hourly -> hourly
    return energy_data


def read_nordpool_data(external_price_csv):
    price_data = pd.read_csv(external_price_csv, index_col=0)
    price_data = price_data.squeeze()
    if price_data.mean() > 100:
        # convert price from SEK per MWh to SEK per kWh
        price_data = price_data / 1000
    price_data.index = pd.to_datetime(price_data.index)
    return price_data


def read_solar_irradiation(irradiation_csv_path):
    """Return solar irradiation, according to SMHI, in Watt per square meter"""
    irradiation_data = pd.read_csv(irradiation_csv_path, index_col=0)
    irradiation_series = irradiation_data['irradiation']
    irradiation_series.index = pd.to_datetime(irradiation_series.index)
    return irradiation_series
