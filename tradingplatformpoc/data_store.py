import datetime
import logging
from typing import Dict, Union

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

from tradingplatformpoc import trading_platform_utils
from tradingplatformpoc.bid import Resource
from tradingplatformpoc.district_heating_calculations import calculate_jan_feb_avg_heating_sold, \
    calculate_peak_day_avg_cons_kw, estimate_district_heating_price, exact_district_heating_price_for_month
from tradingplatformpoc.trading_platform_utils import minus_n_hours


logger = logging.getLogger(__name__)


class DataStore:
    nordpool_data: pd.Series
    irradiation_data: pd.Series
    all_external_heating_sells: pd.Series
    grid_carbon_intensity: pd.Series
    elec_tax: float  # SEK/kWh
    elec_grid_fee: float  # SEK/kWh
    elec_tax_internal: float  # SEK/kWh
    elec_grid_fee_internal: float  # SEK/kWh

    def __init__(self, config_area_info: dict, nordpool_data: pd.Series, irradiation_data: pd.Series,
                 grid_carbon_intensity: pd.Series):
        self.default_pv_area = 0.0  # Assume no pv area as default
        self.default_pv_efficiency = config_area_info["DefaultPVEfficiency"]
        self.heating_wholesale_price_fraction = config_area_info['ExternalHeatingWholesalePriceFraction']
        self.elec_wholesale_offset = config_area_info['ExternalElectricityWholesalePriceOffset']
        self.elec_tax = config_area_info["ElectricityTax"]
        self.elec_grid_fee = config_area_info["ElectricityGridFee"]
        self.elec_tax_internal = config_area_info["ElectricityTaxInternal"]
        self.elec_grid_fee_internal = config_area_info["ElectricityGridFeeInternal"]
        # Square root since it is added both to the BUY and the SELL side
        self.heat_transfer_loss_per_side = 1 - np.sqrt(1 - config_area_info["HeatTransferLoss"])

        self.nordpool_data = nordpool_data
        self.irradiation_data = irradiation_data
        self.all_external_heating_sells = pd.Series(dtype=float)
        self.all_external_heating_sells.index = pd.to_datetime(self.all_external_heating_sells.index, utc=True)
        self.grid_carbon_intensity = grid_carbon_intensity

    @staticmethod
    def from_csv_files(config_area_info: dict, data_path: str = "tradingplatformpoc.data",
                       external_price_file: str = "nordpool_area_grid_el_price.csv",
                       irradiation_file: str = "varberg_irradiation_W_m2_h.csv",
                       electricitymap_file: str = "electricity_co2equivalents_year2019.csv"):

        external_price_csv_path = resource_filename(data_path, external_price_file)
        irradiation_csv_path = resource_filename(data_path, irradiation_file)
        electricitymap_csv_path = resource_filename(data_path, electricitymap_file)

        return DataStore(config_area_info, read_nordpool_data(external_price_csv_path),
                         read_solar_irradiation(irradiation_csv_path),
                         read_electricitymap_csv(electricitymap_csv_path))

    def get_nordpool_price_for_period(self, period: datetime.datetime):
        return self.nordpool_data.loc[period]

    def get_estimated_retail_price(self, period: datetime.datetime, resource: Resource, include_tax: bool) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to sell energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        if resource == Resource.ELECTRICITY:
            # For electricity, the price is known, so 'estimated' and 'exact' are the same
            gross_price = self.get_electricity_gross_retail_price(period)
            if include_tax:
                return self.get_electricity_net_external_price(gross_price)
            else:
                return gross_price
        elif resource == Resource.HEATING:
            # District heating is not taxed
            return estimate_district_heating_price(period)
        else:
            raise RuntimeError('Method not implemented for {}'.format(resource))

    def get_estimated_wholesale_price(self, period: datetime.datetime, resource: Resource) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to buy energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        if resource == Resource.ELECTRICITY:
            return self.get_electricity_wholesale_price(period)
        elif resource == Resource.HEATING:
            return estimate_district_heating_price(period) * self.heating_wholesale_price_fraction
        else:
            raise RuntimeError('Method not implemented for {}'.format(resource))

    def get_exact_retail_price(self, period: datetime.datetime, resource: Resource, include_tax: bool) -> float:
        """Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh"""
        if resource == Resource.ELECTRICITY:
            gross_price = self.get_electricity_gross_retail_price(period)
            if include_tax:
                return self.get_electricity_net_external_price(gross_price)
            else:
                return gross_price
        elif resource == Resource.HEATING:
            # District heating is not taxed
            consumption_this_month_kwh = self.calculate_consumption_this_month(period.year, period.month)
            if consumption_this_month_kwh == 0:
                return handle_no_consumption_when_calculating_heating_price(period)
            jan_feb_avg_consumption_kw = calculate_jan_feb_avg_heating_sold(self.all_external_heating_sells, period)
            prev_month_peak_day_avg_consumption_kw = calculate_peak_day_avg_cons_kw(self.all_external_heating_sells,
                                                                                    period.year, period.month)
            total_cost_for_month = exact_district_heating_price_for_month(period.month, period.year,
                                                                          consumption_this_month_kwh,
                                                                          jan_feb_avg_consumption_kw,
                                                                          prev_month_peak_day_avg_consumption_kw)
            return total_cost_for_month / consumption_this_month_kwh
        else:
            raise RuntimeError('Method not implemented for {}'.format(resource))

    def get_exact_wholesale_price(self, period: datetime.datetime, resource: Resource) -> float:
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""
        if resource == Resource.ELECTRICITY:
            return self.get_electricity_wholesale_price(period)
        elif resource == Resource.HEATING:
            consumption_this_month_kwh = self.calculate_consumption_this_month(period.year, period.month)
            if consumption_this_month_kwh == 0:
                return handle_no_consumption_when_calculating_heating_price(period)
            jan_feb_avg_consumption_kw = calculate_jan_feb_avg_heating_sold(self.all_external_heating_sells, period)
            prev_month_peak_day_avg_consumption_kw = calculate_peak_day_avg_cons_kw(self.all_external_heating_sells,
                                                                                    period.year, period.month)
            total_cost_for_month = exact_district_heating_price_for_month(period.month, period.year,
                                                                          consumption_this_month_kwh,
                                                                          jan_feb_avg_consumption_kw,
                                                                          prev_month_peak_day_avg_consumption_kw)
            return (total_cost_for_month / consumption_this_month_kwh) * self.heating_wholesale_price_fraction

        else:
            raise RuntimeError('Method not implemented for {}'.format(resource))

    def calculate_consumption_this_month(self, year: int, month: int) -> float:
        """
        Calculate the sum of all external heating sells for the specified year-month combination.
        Returns a float with the unit kWh.
        """
        subset = (self.all_external_heating_sells.index.year == year) & \
                 (self.all_external_heating_sells.index.month == month)
        return sum(self.all_external_heating_sells[subset])

    def get_electricity_gross_retail_price(self, period: datetime.datetime) -> float:
        """
        For electricity, the price is known, so 'estimated' and 'exact' are the same.
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        """
        nordpool_price = self.get_nordpool_price_for_period(period)
        return self.get_electricity_gross_retail_price_from_nordpool_price(nordpool_price)

    def get_electricity_gross_retail_price_from_nordpool_price(self, nordpool_price: float) -> float:
        """
        The external grid sells at the Nordpool spot price, plus the "grid fee".
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        """
        return nordpool_price + self.elec_grid_fee

    def get_electricity_net_external_price(self, gross_price: float) -> float:
        """
        Net external price = gross external price (i.e. what the seller receives) + tax
        """
        return gross_price + self.elec_tax

    def get_electricity_net_internal_price(self, gross_price: float) -> float:
        """
        Net internal price = gross price (i.e. what the seller receives) + tax + grid fee
        """
        return gross_price + self.elec_tax_internal + self.elec_grid_fee_internal

    def get_electricity_gross_internal_price(self, net_price: float) -> float:
        """
        Given a "net" price, for example the market clearing price, this method calculates how much a seller actually
        receives after paying taxes and grid fees.
        """
        return net_price - self.elec_tax_internal - self.elec_grid_fee_internal

    def get_electricity_wholesale_price(self, period: datetime.datetime) -> float:
        """
        For electricity, the price is known, so 'estimated' and 'exact' are the same.
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        """
        return self.get_electricity_wholesale_price_from_nordpool_price(self.get_nordpool_price_for_period(period))

    def get_electricity_wholesale_price_from_nordpool_price(self, nordpool_price: float) -> float:
        """
        Wholesale price = Nordpool spot price + self.elec_wholesale_offset
        """
        return nordpool_price + self.elec_wholesale_offset

    def get_nordpool_data_datetimes(self):
        return self.nordpool_data.index.tolist()
    
    def get_nordpool_prices_last_n_hours_dict(self, period: datetime.datetime, go_back_n_hours: int):
        mask = (self.nordpool_data.index < period) & \
            (self.nordpool_data.index >= minus_n_hours(period, go_back_n_hours))
        nordpool_prices_last_n_hours = self.nordpool_data.loc[mask]
        if len(nordpool_prices_last_n_hours.index) != go_back_n_hours:
            logger.info('No Nordpool data before {}. Returning get_nordpool_prices_last_n_hours_dict with {} '
                        'entries instead of the desired {}'.
                        format(nordpool_prices_last_n_hours.index.min(), len(nordpool_prices_last_n_hours.index),
                               go_back_n_hours))
        return nordpool_prices_last_n_hours.to_dict()

    def get_local_price_if_exists_else_external_estimate(self, period: datetime.datetime, clearing_prices_historical:
                                                         Union[Dict[datetime.datetime, Dict[Resource, float]],
                                                               None]) -> Dict[Resource, float]:
        to_return = {}

        if clearing_prices_historical is not None:
            clearing_prices = dict(clearing_prices_historical)
            if period in clearing_prices:
                to_return = clearing_prices[period].copy()  # Copy to avoid modifying clearing_prices_historical
        for resource in trading_platform_utils.ALL_IMPLEMENTED_RESOURCES:
            if (resource not in to_return) or (to_return[resource] is None) or (np.isnan(to_return[resource])):
                logger.debug('For period {}, resource {}, no historical clearing prices available, will use external '
                             'prices instead.'.format(period, resource))
                to_return[resource] = self.get_estimated_retail_price(period, resource, include_tax=True)
        return to_return

    def add_external_heating_sell(self, period: datetime.datetime, external_heating_sell_quantity: float):
        """
        The data_store needs this information to be able to calculate the exact district heating cost.
        Note: When there is 0 heating sold, this still needs to be added as a value - if there are values "missing" in
        self.all_external_heating_sells, then some methods will break (calculate_jan_feb_avg_heating_sold for example)
        """
        if period in self.all_external_heating_sells.index:
            existing_value = self.all_external_heating_sells[period]
            logger.warning('Already had a value for external heating sell for period {}. Was {}, will overwrite it '
                           'with new value {}.'.format(period, existing_value, external_heating_sell_quantity))
            self.all_external_heating_sells[period] = external_heating_sell_quantity
        else:
            to_add_in = pd.Series(external_heating_sell_quantity, index=[period])
            self.all_external_heating_sells = pd.concat([self.all_external_heating_sells, to_add_in])


def read_energy_data(energy_csv_path: str):
    energy_data = pd.read_csv(energy_csv_path, index_col=0)
    energy_data.index = pd.to_datetime(energy_data.index, utc=True)
    return energy_data['tornet_electricity_consumed_household_kwh'], \
        energy_data['coop_electricity_consumed_cooling_kwh'] + \
        energy_data['coop_electricity_consumed_other_kwh'], \
        energy_data['tornet_energy_consumed_heat_kwh'], \
        np.maximum(energy_data['coop_net_heat_consumed'], 0)  # Indications are Coop has no excess heat so setting to 0


def read_nordpool_data(external_price_csv_path: str):
    price_data = pd.read_csv(external_price_csv_path, index_col=0)
    price_data = price_data.squeeze()
    if price_data.mean() > 100:
        # convert price from SEK per MWh to SEK per kWh
        price_data = price_data / 1000
    price_data.index = pd.to_datetime(price_data.index, utc=True)
    return price_data


def read_solar_irradiation(irradiation_csv_path: str):
    """Return solar irradiation, according to SMHI, in Watt per square meter"""
    irradiation_data = pd.read_csv(irradiation_csv_path, index_col=0)
    irradiation_series = irradiation_data['irradiation']
    irradiation_series.index = pd.to_datetime(irradiation_series.index, utc=True)
    return irradiation_series


def read_electricitymap_csv(electricitymap_csv_path: str) -> pd.Series:
    """
    Reads the electricity map CSV file. Returns a pd.Series with the marginal carbon intensity.
    """
    em_data = pd.read_csv(electricitymap_csv_path, delimiter=';')
    em_data.index = pd.to_datetime(em_data['timestamp'], unit='s')
    # The input is in local time, with NA for the times that "don't exist" due to daylight savings time
    em_data = em_data.tz_localize('Europe/Stockholm', nonexistent='NaT', ambiguous='NaT')
    # Now, remove the rows where datetime is NaT (the values there are NA anyway)
    em_data = em_data.loc[~em_data.index.isnull()]
    # Finally, convert to UTC
    em_data = em_data.tz_convert('UTC')
    return em_data['marginal_carbon_intensity_avg']


def handle_no_consumption_when_calculating_heating_price(period):
    logger.warning("Tried to calculate exact external heating price, in SEK/kWh, for {:%B %Y}, but had no "
                   "consumption for this month, so returned np.nan.".format(period))
    return np.nan
