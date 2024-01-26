import math
from datetime import datetime, timezone
from typing import Dict
from unittest import TestCase

import numpy as np

import pandas as pd

from tests import utility_test_objects

from tradingplatformpoc.data.preprocessing import clean, read_nordpool_data
from tradingplatformpoc.market.bid import Action, GrossBid, Resource
from tradingplatformpoc.market.market_solver import no_bids_accepted, resolve_bids
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.price.iprice import IPrice
from tradingplatformpoc.simulation_runner.simulation_utils import net_bids_from_gross_bids
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES, hourly_datetime_array_between

DATETIME_ARRAY = hourly_datetime_array_between(datetime(2018, 12, 31, 23, tzinfo=timezone.utc),
                                               datetime(2020, 1, 31, 22, tzinfo=timezone.utc))
SOME_DATETIME = datetime(2019, 1, 2, tzinfo=timezone.utc)
CONSTANT_NORDPOOL_PRICE = 0.6  # Doesn't matter what this is
ONES_SERIES = pd.Series(np.ones(shape=len(DATETIME_ARRAY)), index=DATETIME_ARRAY)

# Read CSV files
external_price_data = read_nordpool_data()
external_price_data = clean(external_price_data).reset_index()
external_price_data = external_price_data.rename(
    columns={'datetime': 'period', 'dayahead_se3_el_price': 'electricity_price'})
area_info = utility_test_objects.AREA_INFO
pricing: Dict[Resource, IPrice] = {
    Resource.HEATING: HeatingPrice(
        heating_wholesale_price_fraction=area_info['ExternalHeatingWholesalePriceFraction'],
        heat_transfer_loss=area_info["HeatTransferLoss"]),
    Resource.ELECTRICITY: ElectricityPrice(
        elec_wholesale_offset=area_info['ExternalElectricityWholesalePriceOffset'],
        elec_tax=area_info["ElectricityTax"],
        elec_grid_fee=area_info["ElectricityGridFee"],
        elec_tax_internal=area_info["ElectricityTaxInternal"],
        elec_grid_fee_internal=area_info["ElectricityGridFeeInternal"],
        nordpool_data=external_price_data)
}


class TestMarketSolver(TestCase):

    def test_resolve_bids_1(self):
        """Test the clearing price calculation in a very simple example with one seller and one buyer."""
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 1, "Seller1", False),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100, 1.5, "Buyer1", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # Someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 100 kWh at 1.5 SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertEqual(1, clearing_prices[Resource.ELECTRICITY])
        for bid in bids_with_acceptance_status:
            self.assertIsNotNone(bid.accepted_quantity)
            self.assertTrue(bid.accepted_quantity > 0)

    def test_resolve_bids_2(self):
        """Test the clearing price calculation when there are no accepted bids."""
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 1, "Seller1", False),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100, 0.5, "Buyer1", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # Someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 100 kWh at 0.5 SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertEqual(1, clearing_prices[Resource.ELECTRICITY])
        for bid in bids_with_acceptance_status:
            self.assertIsNotNone(bid.accepted_quantity)
            self.assertFalse(bid.accepted_quantity > 0)

    def test_resolve_bids_3(self):
        """Test the clearing price calculation when there are 4 different bids, one of them from an external grid."""
        external_gross_price = 10
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 0, "Seller1", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 1.5, "Seller2", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 10000, external_gross_price, "Grid", True),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 300, math.inf, "Buyer1", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # Someone willing to sell 100 kWh at 0 SEK/kWh,
        # someone willing to sell 100 kWh at 1.5 SEK/kWh,
        # someone willing to sell 10000 kWh at 10 SEK/kWh,
        # someone willing to buy 300 kWh at Inf SEK/kWh.
        # Clearing price should be 10 SEK/kWh
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertEqual(pricing[Resource.ELECTRICITY].get_electricity_net_external_price(external_gross_price),
                         clearing_prices[Resource.ELECTRICITY])
        for bid in bids_with_acceptance_status:
            self.assertTrue(bid.accepted_quantity > 0)

    def test_resolve_bids_4(self):
        """Test the clearing price calculation when there are 4 different bids, and the locally produced energy covers
        the demand."""
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 10000, 2, "Grid", True),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 0.75, "Seller1", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 1, "Seller2", False),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # Top bid being typical for external grid
        # Someone willing to sell 100 kWh at 0.75 SEK/kWh,
        # someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 200 kWh at Inf SEK/kWh.
        # Clearing price should be 1 SEK/kWh
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertEqual(1, clearing_prices[Resource.ELECTRICITY])
        for bid in bids_with_acceptance_status:
            self.assertIsNotNone(bid.accepted_quantity)
            if bid.source == 'Grid':
                self.assertFalse(bid.accepted_quantity > 0)
            else:
                self.assertTrue(bid.accepted_quantity > 0)

    def test_resolve_bids_5(self):
        """
        Test that no bids are deemed 'accepted' and that the clearing price is np.nan when there isn't enough energy to
        satisfy the local demand.
        """
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 0.75, "Seller1", False),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 200, math.inf, "Buyer1", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertTrue(np.isnan(clearing_prices[Resource.ELECTRICITY]))
        for bid in bids_with_acceptance_status:
            self.assertFalse(bid.accepted_quantity > 0)

    def test_resolve_bids_with_no_inf_buy(self):
        """Test the clearing price calculation when there are no buy-bids with Inf asking price."""
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 1, "Seller1", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 1.25, "Seller2", False),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 200, 1.5, "Buyer1", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # Someone willing to sell 100 kWh at 1 SEK/kWh,
        # someone willing to buy 100 kWh at 1.25 SEK/kWh,
        # someone willing to buy 200 kWh at 1.5 SEK/kWh.
        # Clearing price should be 1.0 SEK/kWh
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertEqual(1, clearing_prices[Resource.ELECTRICITY])
        for bid in bids_with_acceptance_status:
            self.assertIsNotNone(bid.accepted_quantity)
            if bid.source == 'Seller2':
                self.assertFalse(bid.accepted_quantity > 0)
            elif bid.source == 'Buyer1':
                self.assertTrue(bid.accepted_quantity > 0)
                self.assertTrue(bid.accepted_quantity < bid.quantity)
            else:
                self.assertAlmostEqual(bid.accepted_quantity, bid.quantity)

    def test_resolve_bids_with_local_surplus(self):
        """Test that the clearing price is calculated correctly when there is a local surplus."""
        bids = [GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 192.76354849517332, math.inf, 'BlockAgent',
                         False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, 0.46069, 'AgentWithBattery', False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 275.3113968, 0.46069, 'PVParkAgent', False),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100.8875027389364, math.inf,
                         'GroceryStoreAgent', False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 10000, 0.89069, 'ElectricityGridAgent',
                         True)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # Local surplus
        # Clearing price should be 0.46069 SEK/kWh
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertEqual(0.46069, clearing_prices[Resource.ELECTRICITY])
        for bid in bids_with_acceptance_status:
            self.assertIsNotNone(bid.accepted_quantity)
            if bid.source == 'ElectricityGridAgent':
                self.assertFalse(bid.accepted_quantity > 0)
            else:
                self.assertTrue(bid.accepted_quantity > 0)

    def test_resolve_bids_with_only_sell_bid_for_heating(self):
        """Test that if for a resource, there are only sell bids and no buy bids, the clearing price is nan. Also, it
        shouldn't break anything for other resources."""
        external_gross_price = 0.8
        bids = [GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 200, math.inf, 'BlockAgent', False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 10000, external_gross_price,
                         'ElectricityGridAgent', True),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.HEATING, 10000, 2.0, 'HeatingGridAgent', True)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # Local surplus
        # Clearing price for electricity should be 0.8 SEK/kWh, for heating np.nan
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertEqual(pricing[Resource.ELECTRICITY].get_electricity_net_external_price(external_gross_price),
                         clearing_prices[Resource.ELECTRICITY])
        self.assertTrue(np.isnan(clearing_prices[Resource.HEATING]))
        for bid in bids_with_acceptance_status:
            self.assertIsNotNone(bid.accepted_quantity)
            if bid.source == 'HeatingGridAgent':
                self.assertFalse(bid.accepted_quantity > 0)
            else:
                self.assertTrue(bid.accepted_quantity > 0)

    def test_resolve_bids_with_two_resources(self):
        """Test that clearing prices are calculated correctly for two resources."""
        external_gross_price = 0.8
        bids = [GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 200, math.inf, 'BlockAgent', False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 10000, external_gross_price,
                         'ElectricityGridAgent', True),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.HEATING, 400, math.inf, 'BlockAgent', False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.HEATING, 10000, 2.0, 'HeatingGridAgent', True)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertEqual(len(ALL_IMPLEMENTED_RESOURCES), len(clearing_prices))
        self.assertEqual(pricing[Resource.ELECTRICITY].get_electricity_net_external_price(external_gross_price),
                         clearing_prices[Resource.ELECTRICITY])
        self.assertEqual(2, clearing_prices[Resource.HEATING])
        for bid in bids_with_acceptance_status:
            self.assertIsNotNone(bid.accepted_quantity)
            self.assertTrue(bid.accepted_quantity > 0)

    def test_no_bids_accepted(self):
        """Test that the no_bids_accepted method doesn't throw a fit when an empty list is passed in."""
        with_acceptance_status = no_bids_accepted([])
        self.assertEqual(0, len(with_acceptance_status))

    def test_res_204(self):
        """The introduction of BUY-bids with price less than Inf, should never increase the local clearing price."""
        retail_price = 1.0
        wholesale_price = 0.5
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, retail_price, "Grid", True),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 4, math.inf, "Buyer", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 5, wholesale_price, "Seller", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # Clearing price should be wholesale_price, since local supply > local demand
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertAlmostEqual(wholesale_price, clearing_prices[Resource.ELECTRICITY])

        # Now add in a storage agent
        storage_buy_price = 0.8
        storage_sell_price = 0.9
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 10000, retail_price, "Grid", True),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 4, math.inf, "Buyer", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 5, wholesale_price, "Seller", False),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 2, storage_buy_price, "Storage", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 2, storage_sell_price, "Storage", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # The storage agent wanting to buy at 0.8 should be ignored, since we have a lower price which satisfies all
        # demand which has asking price = Inf
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertAlmostEqual(wholesale_price, clearing_prices[Resource.ELECTRICITY])
        accepted_bids = [bid for bid in bids_with_acceptance_status if bid.accepted_quantity > 0]
        self.assertEqual(3, len(accepted_bids))

    def test_res_220(self):
        """Quantity of accepted sell bids should be equal to quantity of accepted buy bids - this likely requires
        one or more bid to be _partially_ accepted."""
        retail_price = 1.0
        wholesale_price = 0.5
        storage_buy_price = 0.8
        storage_sell_price = 0.9
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 10000, retail_price, "Grid", True),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 4, math.inf, "Buyer", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 5, wholesale_price, "Seller", False),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 2, storage_buy_price, "Storage", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 2, storage_sell_price, "Storage", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])
        # The storage agent wanting to buy at 0.8 should be ignored, since we have a lower price which satisfies all
        # demand which has asking price = Inf
        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        self.assertAlmostEqual(wholesale_price, clearing_prices[Resource.ELECTRICITY])
        accepted_sell_quantity = sum([bid.accepted_quantity for bid in bids_with_acceptance_status
                                      if bid.action == Action.SELL])
        accepted_buy_quantity = sum([bid.accepted_quantity for bid in bids_with_acceptance_status
                                     if bid.action == Action.BUY])
        self.assertAlmostEqual(accepted_sell_quantity, accepted_buy_quantity)

    def test_partial_acceptance_same_price(self):
        """If multiple bids have the same price, we may require them all to be partially accepted"""
        local_sell_price = 1.5
        bids = [GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 200, local_sell_price, "Seller1", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 200, local_sell_price, "Seller2", False),
                GrossBid(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 10000, 10, "Grid", True),
                GrossBid(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 300, math.inf, "Buyer1", False)]
        net_bids = net_bids_from_gross_bids(bids, pricing[Resource.ELECTRICITY])

        clearing_prices, bids_with_acceptance_status = resolve_bids(SOME_DATETIME, net_bids)
        local_sell_price_plus_tax_and_fee = pricing[Resource.ELECTRICITY].get_electricity_net_internal_price(
            local_sell_price)
        self.assertAlmostEqual(local_sell_price_plus_tax_and_fee, clearing_prices[Resource.ELECTRICITY])
        accepted_sell_quantity = sum([bid.accepted_quantity for bid in bids_with_acceptance_status
                                      if bid.action == Action.SELL])
        accepted_buy_quantity = sum([bid.accepted_quantity for bid in bids_with_acceptance_status
                                     if bid.action == Action.BUY])
        self.assertAlmostEqual(accepted_sell_quantity, accepted_buy_quantity)

        # Seller1 and Seller2 should both be partially accepted
        for bid_with_acceptance_status in bids_with_acceptance_status:
            if bid_with_acceptance_status.source in ["Seller1", "Seller2"]:
                self.assertAlmostEqual(150, bid_with_acceptance_status.accepted_quantity)
