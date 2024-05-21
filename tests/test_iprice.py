from datetime import datetime, timezone
from unittest import TestCase

import numpy as np

import pandas as pd
from pandas import DatetimeIndex

from tests import utility_test_objects

from tradingplatformpoc.data.preprocessing import read_electricitymap_data
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice, calculate_consumption_this_month
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between

FEB_1_1_AM = datetime(2019, 2, 1, 1, 0, 0, tzinfo=timezone.utc)

DATETIME_ARRAY = hourly_datetime_array_between(datetime(2018, 12, 31, 23, tzinfo=timezone.utc),
                                               datetime(2020, 1, 31, 22, tzinfo=timezone.utc))
CONSTANT_NORDPOOL_PRICE = 0.6  # Doesn't matter what this is
ONES_SERIES = pd.Series(np.ones(shape=len(DATETIME_ARRAY)), index=DATETIME_ARRAY)

external_price_data = ONES_SERIES * CONSTANT_NORDPOOL_PRICE

area_info = utility_test_objects.AREA_INFO
heat_pricing: HeatingPrice = HeatingPrice(
    heating_wholesale_price_fraction=area_info['ExternalHeatingWholesalePriceFraction'],
    heat_transfer_loss=area_info["HeatTransferLoss"])
electricity_pricing: ElectricityPrice = ElectricityPrice(
    elec_wholesale_offset=area_info['ExternalElectricityWholesalePriceOffset'],
    elec_tax=area_info["ElectricityTax"],
    elec_transmission_fee=area_info["ElectricityTransmissionFee"],
    elec_effect_fee=area_info["ElectricityEffectFee"],
    elec_tax_internal=area_info["ElectricityTaxInternal"],
    elec_transmission_fee_internal=area_info["ElectricityTransmissionFeeInternal"],
    elec_effect_fee_internal=area_info["ElectricityEffectFeeInternal"],
    nordpool_data=external_price_data)


class TestElectricityPrice(TestCase):

    def test_get_nordpool_price_for_period(self):
        """Test that what we put into data_store is the same as we get out"""
        self.assertEqual(CONSTANT_NORDPOOL_PRICE, electricity_pricing.get_nordpool_price_for_periods(FEB_1_1_AM))

    def test_get_nordpool_price_for_periods(self):
        """Test that what we put into data_store is the same as we get out, when doing multiple periods at a time."""
        prices = electricity_pricing.get_nordpool_price_for_periods(FEB_1_1_AM, 24)
        for price in prices:
            self.assertEqual(CONSTANT_NORDPOOL_PRICE, price)

    def test_estimated_retail_price_greater_than_wholesale_price(self):
        """Test that the retail price is always greater than the wholesale price, even without including taxes"""
        # May want to test for other resources than ELECTRICITY
        for dt in DATETIME_ARRAY:
            retail_price = electricity_pricing.get_estimated_retail_price(dt, include_tax=False)
            wholesale_price = electricity_pricing.get_estimated_wholesale_price(dt)
            self.assertTrue(retail_price > wholesale_price)

    def test_retail_price_offset(self):
        """
        Test that different tax rates and grid fees are reflected in the price we get from get_estimated_retail_price.
        """
        electricity_pricing_2: ElectricityPrice = ElectricityPrice(
            elec_wholesale_offset=0.05,
            elec_tax=1.5,
            elec_transmission_fee=0.5,
            elec_effect_fee=0,
            elec_tax_internal=0,
            elec_transmission_fee_internal=0,
            elec_effect_fee_internal=0,
            nordpool_data=external_price_data)

        # Comparing gross prices
        price_for_normal_ds = electricity_pricing.get_estimated_retail_price(FEB_1_1_AM, include_tax=False)
        self.assertAlmostEqual(0.73, price_for_normal_ds)
        self.assertAlmostEqual(1.1, electricity_pricing_2.get_estimated_retail_price(FEB_1_1_AM, include_tax=False))
        # Comparing net prices
        price_for_normal_ds = electricity_pricing.get_estimated_retail_price(FEB_1_1_AM, include_tax=True)
        self.assertAlmostEqual(1.09, price_for_normal_ds)
        self.assertAlmostEqual(2.6, electricity_pricing_2.get_estimated_retail_price(FEB_1_1_AM, include_tax=True))

    def test_read_electricitymap_csv(self):
        """Test that the CSV file with ElectricityMap carbon intensity data reads correctly."""
        data = read_electricitymap_data()
        self.assertTrue(data.shape[0] > 0)
        self.assertIsInstance(data.index, DatetimeIndex)

    def test_very_negative_nordpool_price(self):
        """Test that the lower_bound parameter of get_exact_retail_prices works as expected"""
        electricity_pricing.nordpool_data[DATETIME_ARRAY[0]] = -10.0
        self.assertEqual(0.0, electricity_pricing.get_exact_retail_prices(DATETIME_ARRAY[0], 1, True, 0.0))
        # Test for more than 1 period as well:
        self.assertEqual(0.0, electricity_pricing.get_exact_retail_prices(DATETIME_ARRAY[0], 2, True, 0.0).iloc[0])

    def test_get_effect_fee_per_day(self):
        """Test that get_effect_fee_per_day works as expected"""
        effect_fee = 35
        electricity_pricing_3: ElectricityPrice = electricity_pricing
        electricity_pricing_3.effect_fee = effect_fee
        fee_per_day = electricity_pricing_3.get_effect_fee_per_day(datetime(2024, 5, 1))
        self.assertEqual(effect_fee / 31, fee_per_day)


class TestHeatingPrice(TestCase):

    def test_add_external_heating_sell(self):
        ds = HeatingPrice(
            heating_wholesale_price_fraction=area_info['ExternalHeatingWholesalePriceFraction'],
            heat_transfer_loss=area_info["HeatTransferLoss"])
        self.assertEqual(0, len(ds.all_external_sells))
        ds.add_external_sell(FEB_1_1_AM, 50.0)
        self.assertEqual(1, len(ds.all_external_sells))

    def test_add_external_heating_sell_where_already_exists(self):
        ds = HeatingPrice(
            heating_wholesale_price_fraction=area_info['ExternalHeatingWholesalePriceFraction'],
            heat_transfer_loss=area_info["HeatTransferLoss"])
        self.assertEqual(0, len(ds.all_external_sells))
        ds.add_external_sell(FEB_1_1_AM, 50.0)
        self.assertEqual(1, len(ds.all_external_sells))
        self.assertAlmostEqual(50.0, ds.all_external_sells[FEB_1_1_AM])
        # Now add more for the same period
        ds.add_external_sell(FEB_1_1_AM, 70.0)
        # Then test that the result of the operation is expected
        self.assertEqual(1, len(ds.all_external_sells))
        self.assertAlmostEqual(120.0, ds.all_external_sells[FEB_1_1_AM])

    def test_calculate_consumption_this_month(self):
        """Test basic functionality of calculate_consumption_this_month"""
        ds = HeatingPrice(
            heating_wholesale_price_fraction=area_info['ExternalHeatingWholesalePriceFraction'],
            heat_transfer_loss=area_info["HeatTransferLoss"])
        ds.add_external_sell(FEB_1_1_AM, 50)
        ds.add_external_sell(datetime(2019, 3, 1, 1, tzinfo=timezone.utc), 100)
        self.assertAlmostEqual(50.0, calculate_consumption_this_month(ds.all_external_sells, 2019, 2))
        self.assertAlmostEqual(0.0, calculate_consumption_this_month(ds.all_external_sells, 2019, 4))

    def test_get_exact_retail_price_heating(self):
        """Test basic functionality of get_exact_retail_price for HIGH_TEMP_HEAT"""
        ds = HeatingPrice(
            heating_wholesale_price_fraction=area_info['ExternalHeatingWholesalePriceFraction'],
            heat_transfer_loss=area_info["HeatTransferLoss"])
        ds.add_external_sell(datetime(2019, 2, 1, 1, tzinfo=timezone.utc), 100)
        ds.add_external_sell(datetime(2019, 3, 1, 1, tzinfo=timezone.utc), 100)
        ds.add_external_sell(datetime(2019, 3, 1, 2, tzinfo=timezone.utc), 140)
        ds.add_external_sell(datetime(2019, 3, 2, 1, tzinfo=timezone.utc), 50)
        ds.add_external_sell(datetime(2019, 3, 2, 2, tzinfo=timezone.utc), 50)
        ds.add_external_sell(datetime(2019, 3, 2, 3, tzinfo=timezone.utc), 50)
        self.assertAlmostEqual(26.230860554970143,
                               ds.get_exact_retail_price(datetime(2019, 3, 2, 3), include_tax=True))

    def test_heating_tax(self):
        """Test that unless anything else is specified, the tax is 0."""
        self.assertEqual(0, heat_pricing.tax)

    def test_approx_heat_price(self):
        """Test the estimated price for different months."""
        self.assertEqual(1.252414798614908, heat_pricing.estimate_district_heating_price(datetime(2019, 1, 1)))
        # Small difference Jan-Feb due to Feb having less days, thus P(today is peak day) is slightly higher
        self.assertEqual(1.2622074253430187, heat_pricing.estimate_district_heating_price(datetime(2019, 2, 1)))
        self.assertEqual(0.5913978494623656, heat_pricing.estimate_district_heating_price(datetime(2019, 3, 1)))
