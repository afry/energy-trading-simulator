import datetime
import logging

import pandas as pd

from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.price.iprice import IPrice
from tradingplatformpoc.trading_platform_utils import minus_n_hours


logger = logging.getLogger(__name__)


class ElectricityPrice(IPrice):
    nordpool_data: pd.Series
    elec_wholesale_offset: float
    elec_tax: float  # SEK/kWh
    elec_grid_fee: float  # SEK/kWh
    elec_tax_internal: float  # SEK/kWh
    elec_grid_fee_internal: float  # SEK/kWh

    def __init__(self, elec_wholesale_offset: float, elec_tax: float, elec_grid_fee: float,
                 elec_tax_internal: float, elec_grid_fee_internal: float, nordpool_data: pd.Series):
        super().__init__(Resource.ELECTRICITY)
        self.nordpool_data = nordpool_data
        self.elec_wholesale_offset = elec_wholesale_offset
        self.elec_tax = elec_tax
        self.elec_grid_fee = elec_grid_fee
        self.elec_tax_internal = elec_tax_internal
        self.elec_grid_fee_internal = elec_grid_fee_internal
    
    def get_estimated_retail_price(self, period: datetime.datetime, include_tax: bool) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to sell energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """

        # For electricity, the price is known, so 'estimated' and 'exact' are the same
        gross_price = self.get_electricity_gross_retail_price(period)
        if include_tax:
            return self.get_electricity_net_external_price(gross_price)
        else:
            return gross_price

    def get_estimated_wholesale_price(self, period: datetime.datetime) -> float:
        """
        Returns the price at which the external grid operator is believed to be willing to buy energy, in SEK/kWh.
        For some energy carriers the price may be known, but for others it may in fact be set after the fact. That is
        why this method is named 'estimated'.
        """
        return self.get_electricity_wholesale_price(period)

    def get_exact_retail_price(self, period: datetime.datetime, include_tax: bool) -> float:
        """Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh"""
        gross_price = self.get_electricity_gross_retail_price(period)
        if include_tax:
            return self.get_electricity_net_external_price(gross_price)
        else:
            return gross_price

    def get_exact_wholesale_price(self, period: datetime.datetime) -> float:
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""

        return self.get_electricity_wholesale_price(period)

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
    
    def get_nordpool_price_for_period(self, period: datetime.datetime):
        return self.nordpool_data.loc[period]
    
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

    def get_external_price_data_datetimes(self):
        return self.nordpool_data.index.tolist()
