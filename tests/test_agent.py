import unittest
from datetime import datetime, timezone
from unittest import TestCase

import numpy as np

import pandas as pd

from tests import utility_test_objects

from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market, Trade
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between

SOME_DATETIME = datetime(2019, 2, 1, 1, tzinfo=timezone.utc)

MAX_NORDPOOL_PRICE = 4.0

MIN_NORDPOOL_PRICE = 0.1
DATETIME_ARRAY = hourly_datetime_array_between(datetime(2018, 12, 31, 23, tzinfo=timezone.utc),
                                               datetime(2020, 1, 31, 22, tzinfo=timezone.utc))

# To make tests consistent, set a random seed
np.random.seed(1)
# Create data
nordpool_values = np.random.uniform(MIN_NORDPOOL_PRICE, MAX_NORDPOOL_PRICE, len(DATETIME_ARRAY))
irradiation_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
carbon_values = np.ones(shape=len(DATETIME_ARRAY))

# Read CSV files
irradiation_data = pd.Series(irradiation_values, index=DATETIME_ARRAY)
external_price_data = pd.Series(nordpool_values, index=DATETIME_ARRAY)

area_info = utility_test_objects.AREA_INFO
heat_pricing: HeatingPrice = HeatingPrice(
    heating_wholesale_price_fraction=area_info['ExternalHeatingWholesalePriceFraction'],
    heat_transfer_loss=area_info["HeatTransferLoss"])
electricity_pricing: ElectricityPrice = ElectricityPrice(
    elec_wholesale_offset=area_info['ExternalElectricityWholesalePriceOffset'],
    elec_tax=area_info["ElectricityTax"],
    elec_grid_fee=area_info["ElectricityGridFee"],
    elec_tax_internal=area_info["ElectricityTaxInternal"],
    elec_grid_fee_internal=area_info["ElectricityGridFeeInternal"],
    nordpool_data=external_price_data)


class TestGridAgent(unittest.TestCase):
    electricity_grid_agent = GridAgent(True, electricity_pricing, Resource.ELECTRICITY, True,
                                       guid='ElectricityGridAgent')
    heating_grid_agent = GridAgent(True, heat_pricing, Resource.HEATING, False,
                                   guid='HeatingGridAgent')

    def test_make_bids_electricity(self):
        """Test basic functionality of GridAgent's make_bids method, for the ELECTRICITY resource."""
        bids = self.electricity_grid_agent.make_bids(SOME_DATETIME)
        self.assertEqual(1, len(bids))
        self.assertEqual(Resource.ELECTRICITY, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)

    def test_make_bids_heating(self):
        """Test basic functionality of GridAgent's make_bids method, for the HEATING resource."""
        bids = self.heating_grid_agent.make_bids(SOME_DATETIME)
        self.assertEqual(1, len(bids))
        self.assertEqual(Resource.HEATING, bids[0].resource)
        self.assertEqual(Action.SELL, bids[0].action)
        self.assertTrue(bids[0].quantity > 0)

    def test_calculate_trades_1(self):
        """Test basic functionality of GridAgent's calculate_external_trades method when there is a local deficit."""
        retail_price = 3.948725389630498
        clearing_prices = {Resource.ELECTRICITY: retail_price, Resource.HEATING: np.nan}
        trades_excl_external = [
            Trade(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BlockAgent", False,
                  Market.LOCAL)
        ]
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, clearing_prices)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.SELL, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(trades_excl_external[0].quantity_pre_loss, external_trades[0].quantity_post_loss)
        self.assertAlmostEqual(retail_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(SOME_DATETIME, external_trades[0].period)

    def test_calculate_trades_1_heating(self):
        """Ensure that the "pre-loss-quantity" of BUY-trades equal the "post-loss-quantity" of SELL trades."""
        retail_price = 1.2622074253430187
        clearing_prices = {Resource.ELECTRICITY: np.nan, Resource.HEATING: retail_price}
        trades_excl_external = [
            Trade(SOME_DATETIME, Action.BUY, Resource.HEATING, 100, retail_price, "BlockAgent", False, Market.LOCAL,
                  self.heating_grid_agent.resource_loss_per_side)
        ]
        external_trades = self.heating_grid_agent.calculate_external_trades(trades_excl_external, clearing_prices)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.SELL, external_trades[0].action)
        self.assertEqual(Resource.HEATING, external_trades[0].resource)
        self.assertEqual(trades_excl_external[0].quantity_pre_loss, external_trades[0].quantity_post_loss)
        self.assertAlmostEqual(retail_price, external_trades[0].price)
        self.assertEqual("HeatingGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(SOME_DATETIME, external_trades[0].period)

    def test_calculate_trades_local_equilibrium(self):
        """Test the calculate_external_trades method when there is no need for any external trades."""
        retail_price = 0.99871
        clearing_prices = {Resource.ELECTRICITY: retail_price, Resource.HEATING: np.nan}
        trades_excl_external = [
            Trade(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BlockAgent", False,
                  Market.LOCAL),
            Trade(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 100, retail_price, "PVParkAgent", False,
                  Market.LOCAL)
        ]
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, clearing_prices)
        self.assertEqual(0, len(external_trades))

    def test_calculate_trades_price_not_matching(self):
        """Test that a warning is logged when the local price is specified as greater than the external retail price."""
        local_price = MAX_NORDPOOL_PRICE + 1.0
        clearing_prices = {Resource.ELECTRICITY: local_price, Resource.HEATING: np.nan}
        trades_excl_external = [
            Trade(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100, local_price, "BlockAgent", False,
                  Market.LOCAL)
        ]
        with self.assertLogs() as captured:
            self.electricity_grid_agent.calculate_external_trades(trades_excl_external, clearing_prices)
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(captured.records[0].levelname, 'WARNING')

    def test_calculate_trades_price_not_matching_2(self):
        """Test calculate_external_trades when local price is lower than the retail price, but there is a need for
        importing of energy. This will lead to penalisation of someone, but shouldn't raise an error."""
        local_price = MIN_NORDPOOL_PRICE - 1.0
        clearing_prices = {Resource.ELECTRICITY: local_price, Resource.HEATING: np.nan}
        trades_excl_external = [
            Trade(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100, local_price, "BlockAgent", False,
                  Market.LOCAL)
        ]
        # Should log a line about external grid and market clearing price being different
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, clearing_prices)
        self.assertEqual(1, len(external_trades))

    def test_calculate_trades_2(self):
        """Test basic functionality of GridAgent's calculate_external_trades method when there is a local surplus."""
        wholesale_price = 3.5087253896304977
        clearing_prices = {Resource.ELECTRICITY: wholesale_price, Resource.HEATING: np.nan}
        trades_excl_external = [
            Trade(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100, wholesale_price, "BlockAgent", False,
                  Market.LOCAL),
            Trade(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 200, wholesale_price, "GSAgent", False,
                  Market.LOCAL),
            Trade(SOME_DATETIME, Action.SELL, Resource.ELECTRICITY, 400, wholesale_price, "PvAgent", False,
                  Market.LOCAL)
        ]
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, clearing_prices)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.BUY, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(100, external_trades[0].quantity_post_loss)
        self.assertAlmostEqual(wholesale_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(SOME_DATETIME, external_trades[0].period)

    def test_calculate_trades_with_some_bids_with_other_resource(self):
        """When sent into an electricity grid agent, heating trades should be ignored."""
        retail_price = 3.948725389630498
        clearing_prices = {Resource.ELECTRICITY: retail_price, Resource.HEATING: np.nan}
        trades_excl_external = [
            Trade(SOME_DATETIME, Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BlockAgent", False,
                  Market.LOCAL),
            Trade(SOME_DATETIME, Action.BUY, Resource.HEATING, 100, retail_price, "BlockAgent", False,
                  Market.LOCAL)
        ]
        external_trades = self.electricity_grid_agent.calculate_external_trades(trades_excl_external, clearing_prices)
        self.assertEqual(1, len(external_trades))
        self.assertEqual(Action.SELL, external_trades[0].action)
        self.assertEqual(Resource.ELECTRICITY, external_trades[0].resource)
        self.assertEqual(trades_excl_external[0].quantity_pre_loss, external_trades[0].quantity_post_loss)
        self.assertAlmostEqual(retail_price, external_trades[0].price)
        self.assertEqual("ElectricityGridAgent", external_trades[0].source)
        self.assertEqual(Market.LOCAL, external_trades[0].market)
        self.assertEqual(SOME_DATETIME, external_trades[0].period)

    def test_calculate_trades_multiple_periods(self):
        """When trades for more than 1 period are sent into calculate_external_trades, an error should be raised"""
        retail_price = 1.0
        clearing_prices = {Resource.ELECTRICITY: retail_price, Resource.HEATING: np.nan}
        trades_excl_external = [
            Trade(DATETIME_ARRAY[0], Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BlockAgent", False,
                  Market.LOCAL),
            Trade(DATETIME_ARRAY[1], Action.BUY, Resource.ELECTRICITY, 100, retail_price, "BlockAgent", False,
                  Market.LOCAL)
        ]
        with self.assertRaises(RuntimeError):
            self.electricity_grid_agent.calculate_external_trades(trades_excl_external, clearing_prices)


class TestBlockAgent(TestCase):
    # Won't test exact values so don't need to set random seed
    elec_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    heat_values = np.random.uniform(0, 100.0, len(DATETIME_ARRAY))
    static_digital_twin_cons = StaticDigitalTwin(1000.0, electricity_usage=pd.Series(elec_values, index=DATETIME_ARRAY),
                                                 space_heating_usage=pd.Series(heat_values, index=DATETIME_ARRAY))
    block_agent_cons = BlockAgent(True, heat_pricing=heat_pricing, electricity_pricing=electricity_pricing,
                                  digital_twin=static_digital_twin_cons, can_sell_heat_to_external=False)
    static_digital_twin_prod = StaticDigitalTwin(1000.0,
                                                 electricity_usage=-pd.Series(elec_values, index=DATETIME_ARRAY),
                                                 space_heating_usage=-pd.Series(heat_values, index=DATETIME_ARRAY))
    block_agent_prod = BlockAgent(True, heat_pricing=heat_pricing, electricity_pricing=electricity_pricing,
                                  digital_twin=static_digital_twin_prod, can_sell_heat_to_external=False)
    static_digital_twin_zeros = StaticDigitalTwin(1000.0,
                                                  electricity_usage=pd.Series(elec_values * 0, index=DATETIME_ARRAY),
                                                  space_heating_usage=pd.Series(heat_values * 0, index=DATETIME_ARRAY))
    block_agent_zeros = BlockAgent(True, heat_pricing=heat_pricing, electricity_pricing=electricity_pricing,
                                   digital_twin=static_digital_twin_zeros, can_sell_heat_to_external=False)

    def test_make_prognosis(self):
        """Test basic functionality of BlockAgent's make_prognosis method."""
        prognosis_consumer = self.block_agent_cons.make_prognosis_for_resource(SOME_DATETIME, Resource.ELECTRICITY)
        self.assertFalse(np.isnan(prognosis_consumer))
        self.assertTrue(prognosis_consumer > 0)
        prognosis_producer = self.block_agent_prod.make_prognosis_for_resource(SOME_DATETIME, Resource.ELECTRICITY)
        self.assertFalse(np.isnan(prognosis_producer))
        self.assertTrue(prognosis_producer < 0)

    def test_make_prognosis_for_first_data_point(self):
        """BlockAgent's make_prognosis method currently just looks up the previous actual value, so here we test
        what happens when we try to make a prognosis for the first value."""
        prognosis_consumer = self.block_agent_cons.make_prognosis_for_resource(DATETIME_ARRAY[0], Resource.ELECTRICITY)
        self.assertFalse(np.isnan(prognosis_consumer))
        self.assertTrue(prognosis_consumer > 0)
        prognosis_producer = self.block_agent_prod.make_prognosis_for_resource(DATETIME_ARRAY[0], Resource.ELECTRICITY)
        self.assertFalse(np.isnan(prognosis_producer))
        self.assertTrue(prognosis_producer < 0)

    def test_get_actual_usage(self):
        """Test basic functionality of BlockAgent's get_actual_usage method."""
        usage_consumer = self.block_agent_cons.get_actual_usage_for_resource(SOME_DATETIME, Resource.ELECTRICITY)
        self.assertFalse(np.isnan(usage_consumer))
        self.assertTrue(usage_consumer > 0)
        usage_producer = self.block_agent_prod.get_actual_usage_for_resource(SOME_DATETIME, Resource.ELECTRICITY)
        self.assertFalse(np.isnan(usage_producer))
        self.assertTrue(usage_producer < 0)
