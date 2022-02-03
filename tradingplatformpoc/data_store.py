import datetime
import logging

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

from tradingplatformpoc.bid import Resource
from tradingplatformpoc.district_heating_calculations import estimate_district_heating_price, \
    exact_district_heating_price_for_month
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod, minus_n_hours

HEATING_WHOLESALE_PRICE_FRACTION = 0.5  # External grid buys heating at 50% of the price they buy for - quite arbitrary

ELECTRICITY_WHOLESALE_PRICE_OFFSET = 0.05
ELECTRICITY_RETAIL_PRICE_OFFSET = 0.48

logger = logging.getLogger(__name__)


class DataStore:
    nordpool_data: pd.Series
    tornet_park_pv_prod: pd.Series
    coop_pv_prod: pd.Series  # Rooftop PV production

    def __init__(self, config_area_info: dict, nordpool_data: pd.Series, irradiation_data: pd.Series):
        self.pv_efficiency = config_area_info["PVEfficiency"]
        self.store_pv_area = config_area_info["StorePVArea"]
        self.park_pv_area = config_area_info["ParkPVArea"]

        self.nordpool_data = nordpool_data
        self.coop_pv_prod = calculate_solar_prod(irradiation_data, self.store_pv_area, self.pv_efficiency)
        self.tornet_park_pv_prod = calculate_solar_prod(irradiation_data, self.park_pv_area, self.pv_efficiency)

    @staticmethod
    def from_csv_files(config_area_info: dict, data_path: str = "tradingplatformpoc.data",
                       external_price_file: str = "nordpool_area_grid_el_price.csv",
                       irradiation_file: str = "varberg_irradiation_W_m2_h.csv"):

        external_price_csv_path = resource_filename(data_path, external_price_file)
        irradiation_csv_path = resource_filename(data_path, irradiation_file)

        return DataStore(config_area_info, read_nordpool_data(external_price_csv_path),
                         read_solar_irradiation(irradiation_csv_path))

    def get_nordpool_price_for_period(self, period: datetime.datetime):
        return self.nordpool_data.loc[period]

    def get_estimated_retail_price(self, period: datetime.datetime, resource: Resource):
        """
        Returns the price at which the external grid operator is believed to be willing to sell energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        if resource == Resource.ELECTRICITY:
            """For electricity, the price is known, so 'estimated' and 'exact' are the same."""
            return self.get_electricity_retail_price(period)
        elif resource == Resource.HEATING:
            return estimate_district_heating_price(period)
        else:
            raise RuntimeError('Method not implemented for {}'.format(resource))

    def get_estimated_wholesale_price(self, period: datetime.datetime, resource: Resource):
        """
        Returns the price at which the external grid operator is believed to be willing to buy energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        if resource == Resource.ELECTRICITY:
            return self.get_electricity_wholesale_price(period)
        elif resource == Resource.HEATING:
            return estimate_district_heating_price(period) * HEATING_WHOLESALE_PRICE_FRACTION
        else:
            raise RuntimeError('Method not implemented for {}'.format(resource))

    def get_exact_retail_price(self, period: datetime.datetime, resource: Resource):
        """Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh"""
        if resource == Resource.ELECTRICITY:
            return self.get_electricity_retail_price(period)
        elif resource == Resource.HEATING:
            # TODO: Calculate these in some way
            consumption_this_month_kwh = 0
            jan_feb_avg_consumption_kw = 0
            prev_month_peak_day_avg_consumption_kw = 0
            return exact_district_heating_price_for_month(period.month, period.year, consumption_this_month_kwh,
                                                          jan_feb_avg_consumption_kw,
                                                          prev_month_peak_day_avg_consumption_kw)
        else:
            raise RuntimeError('Method not implemented for {}'.format(resource))

    def get_exact_wholesale_price(self, period: datetime.datetime, resource: Resource):
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""
        if resource == Resource.ELECTRICITY:
            return self.get_electricity_wholesale_price(period)
        elif resource == Resource.HEATING:
            # TODO: Calculate these in some way
            consumption_this_month_kwh = 0
            jan_feb_avg_consumption_kw = 0
            prev_month_peak_day_avg_consumption_kw = 0
            return exact_district_heating_price_for_month(period.month, period.year, consumption_this_month_kwh,
                                                          jan_feb_avg_consumption_kw,
                                                          prev_month_peak_day_avg_consumption_kw) * \
                HEATING_WHOLESALE_PRICE_FRACTION
        else:
            raise RuntimeError('Method not implemented for {}'.format(resource))

    def get_electricity_retail_price(self, period):
        """
        For electricity, the price is known, so 'estimated' and 'exact' are the same.
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        """
        return self.get_nordpool_price_for_period(period) + ELECTRICITY_RETAIL_PRICE_OFFSET

    def get_electricity_wholesale_price(self, period):
        """
        For electricity, the price is known, so 'estimated' and 'exact' are the same.
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        """
        return self.get_nordpool_price_for_period(period) + ELECTRICITY_WHOLESALE_PRICE_OFFSET

    def get_nordpool_data_datetimes(self):
        return self.nordpool_data.index.tolist()

    def get_nordpool_prices_last_n_hours_dict(self, period: datetime.datetime, go_back_n_hours: int):
        nordpool_prices_last_n_hours = {}
        for i in range(go_back_n_hours):
            t = minus_n_hours(period, i + 1)
            try:
                nordpool_prices_last_n_hours[t] = self.get_nordpool_price_for_period(t)
            except KeyError:
                logger.info('No Nordpool data on or before {}. Exiting get_nordpool_prices_last_n_hours_dict with {} '
                            'entries instead of the desired {}'.
                            format(t, len(nordpool_prices_last_n_hours), go_back_n_hours))
                break
        return nordpool_prices_last_n_hours


def read_energy_data(energy_csv_path: str):
    energy_data = pd.read_csv(energy_csv_path, index_col=0)
    energy_data.index = pd.to_datetime(energy_data.index)
    return energy_data['tornet_electricity_consumed_household_kwh'], \
        energy_data['coop_electricity_consumed_cooling_kwh'] + \
        energy_data['coop_electricity_consumed_other_kwh'], \
        energy_data['tornet_energy_consumed_heat_kwh'], \
        np.maximum(energy_data['coop_net_heat_consumed'], 0)  # Indications are Coop has no excess heat so setting to 0


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
    energy_data['Timestamp'] = pd.to_datetime(energy_data['Reading Date'] + " " + energy_data['Time'],
                                              format='%Y-%m-%d %H:%M')
    energy_data = energy_data.sort_values(by=['Timestamp'])
    energy_data = energy_data.set_index('Timestamp')
    energy_data = energy_data.rename({'Energy': 'Energy [kWh]'}, axis=1)
    energy_data = energy_data['Energy [kWh]']
    energy_data = energy_data.resample('1H').sum() / 2  # Half-hourly -> hourly. Data seems to be kWh/h, hence the /2
    return energy_data


def read_nordpool_data(external_price_csv_path: str):
    price_data = pd.read_csv(external_price_csv_path, index_col=0)
    price_data = price_data.squeeze()
    if price_data.mean() > 100:
        # convert price from SEK per MWh to SEK per kWh
        price_data = price_data / 1000
    price_data.index = pd.to_datetime(price_data.index)
    return price_data


def read_solar_irradiation(irradiation_csv_path: str):
    """Return solar irradiation, according to SMHI, in Watt per square meter"""
    irradiation_data = pd.read_csv(irradiation_csv_path, index_col=0)
    irradiation_series = irradiation_data['irradiation']
    irradiation_series.index = pd.to_datetime(irradiation_series.index)
    return irradiation_series
