import datetime
import logging
from typing import Union

import pandas as pd

from tradingplatformpoc.market.trade import Market, Resource
from tradingplatformpoc.price.iprice import IPrice


logger = logging.getLogger(__name__)


class ElectricityPrice(IPrice):
    nordpool_data: pd.Series
    transmission_fee: float  # SEK/kWh
    effect_fee: float  # SEK/kW
    elec_tax_internal: float  # SEK/kWh
    elec_transmission_fee_internal: float  # SEK/kWh
    elec_effect_fee_internal: float  # SEK/kW

    def __init__(self, elec_wholesale_offset: float,
                 elec_tax: float, elec_transmission_fee: float, elec_effect_fee: float,
                 elec_tax_internal: float, elec_transmission_fee_internal: float, elec_effect_fee_internal: float,
                 nordpool_data: pd.Series):
        super().__init__(Resource.ELECTRICITY)
        self.nordpool_data = nordpool_data
        self.wholesale_offset = elec_wholesale_offset
        self.tax = elec_tax
        self.transmission_fee = elec_transmission_fee
        self.effect_fee = elec_effect_fee
        self.elec_tax_internal = elec_tax_internal
        self.elec_transmission_fee_internal = elec_transmission_fee_internal
        self.elec_effect_fee_internal = elec_effect_fee_internal

        self.grid_fee = self.transmission_fee + self.effect_fee / 8766.0
        self.elec_grid_fee_internal = self.elec_transmission_fee_internal + self.elec_effect_fee_internal / 8766.0

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
        return self.get_exact_retail_prices(period, 1, include_tax)

    def get_exact_wholesale_price(self, period: datetime.datetime) -> float:
        """Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh"""
        return self.get_exact_wholesale_prices(period, 1)

    def get_exact_retail_prices(self, period: datetime.datetime, length: int, include_tax: bool,
                                lower_bound: float = -999.0) -> Union[float, pd.Series]:
        """
        Returns the price at which the external grid operator is willing to sell energy, in SEK/kWh, for the
        start_period and length periods forwards.
        """
        gross_price = self.get_electricity_gross_retail_price(period, length)
        if include_tax:
            retail_price = self.get_electricity_net_external_price(gross_price)
        else:
            retail_price = gross_price
        if isinstance(retail_price, float):
            return max(lower_bound, retail_price)
        return retail_price.clip(lower_bound)

    def get_exact_wholesale_prices(self, period: datetime.datetime, length: int) -> Union[float, pd.Series]:
        """
        Returns the price at which the external grid operator is willing to buy energy, in SEK/kWh, for the
        start_period and length periods forwards.
        """
        return self.get_electricity_wholesale_price(period, length)

    def get_electricity_gross_retail_price(self, period: datetime.datetime, length: int = 1) -> Union[float, pd.Series]:
        """
        For electricity, the price is known, so 'estimated' and 'exact' are the same.
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        """
        nordpool_price = self.get_nordpool_price_for_periods(period, length)
        return self.get_electricity_gross_retail_price_from_nordpool_price(nordpool_price)
    
    def get_electricity_gross_retail_price_from_nordpool_price(self, nordpool_price: Union[float, pd.Series]) \
            -> Union[float, pd.Series]:
        """
        The external grid sells at the Nordpool spot price, plus the "grid fee".
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        """
        # TODO: Will not be needed anymore when Chalmers' optimizer uses the effect fee "properly"
        return nordpool_price + self.grid_fee

    def get_electricity_net_external_price(self, gross_price: Union[float, pd.Series]) -> Union[float, pd.Series]:
        """
        Net external price = gross external price (i.e. what the seller receives) + tax
        """
        return gross_price + self.tax

    def get_electricity_net_internal_price(self, gross_price: Union[float, pd.Series]) -> Union[float, pd.Series]:
        """
        Net internal price = gross price (i.e. what the seller receives) + tax + grid fee
        """
        return gross_price + self.elec_tax_internal + self.elec_grid_fee_internal

    def get_electricity_gross_internal_price(self, net_price: Union[float, pd.Series]) -> Union[float, pd.Series]:
        """
        Given a "net" price, for example the market clearing price, this method calculates how much a seller actually
        receives after paying taxes and grid fees.
        """
        return net_price - self.elec_tax_internal - self.elec_grid_fee_internal

    def get_electricity_wholesale_price(self, period: datetime.datetime, length: int = 1) -> Union[float, pd.Series]:
        """
        For electricity, the price is known, so 'estimated' and 'exact' are the same.
        See also https://doc.afdrift.se/pages/viewpage.action?pageId=17072325
        """
        nordpool_prices = self.get_nordpool_price_for_periods(period, length)
        return self.get_electricity_wholesale_price_from_nordpool_price(nordpool_prices)

    def get_electricity_wholesale_price_from_nordpool_price(self, nordpool_price: Union[float, pd.Series]) \
            -> Union[float, pd.Series]:
        """
        Wholesale price = Nordpool spot price + self.elec_wholesale_offset
        """
        return nordpool_price + self.wholesale_offset

    def get_nordpool_price_for_periods(self, start_period: datetime.datetime, length: int = 1) \
            -> Union[float, pd.Series]:
        if length == 1:
            return self.nordpool_data.loc[start_period]
        start_index = self.nordpool_data.index.get_loc(start_period)
        end_index = start_index + length
        return self.nordpool_data.iloc[start_index:end_index]

    def get_tax(self, market: Market) -> float:
        return self.elec_tax_internal if market == Market.LOCAL else self.tax

    def get_grid_fee(self, market: Market) -> float:
        return self.elec_grid_fee_internal if market == Market.LOCAL else self.grid_fee
