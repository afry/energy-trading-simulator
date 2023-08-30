# import datetime
import datetime
from unittest import TestCase, mock

import numpy as np

import pandas as pd

from pkg_resources import resource_filename

from tradingplatformpoc.config.access_config import read_config
from tradingplatformpoc.generate_data.mock_data_generation_functions import get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.market.trade import Market, Trade
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.simulation_runner.simulation_utils import construct_df_from_datetime_dict, \
    get_external_heating_prices, get_quantity_heating_sold_by_external_grid
from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator
from tradingplatformpoc.sql.job.models import uuid_as_str_generator
from tradingplatformpoc.trading_platform_utils import hourly_datetime_array_between


class Test(TestCase):

    mock_datas_file_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
    config = read_config()
    heat_pricing: HeatingPrice = HeatingPrice(
        heating_wholesale_price_fraction=config['AreaInfo']['ExternalHeatingWholesalePriceFraction'],
        heat_transfer_loss=config['AreaInfo']["HeatTransferLoss"])

    def test_initialize_agents(self):
        """Test that an error is thrown if no GridAgents are initialized."""
        fake_config = {'Agents': [agent for agent in self.config['Agents'] if agent['Type'] != 'GridAgent'],
                       'AreaInfo': self.config['AreaInfo'],
                       'MockDataConstants': self.config['MockDataConstants']}
        agent_specs = {agent['Name']: uuid_as_str_generator() for agent in fake_config['Agents'][:]
                       if agent['Type'] == 'BuildingAgent'}
        mock_data_columns = [[get_elec_cons_key(agent_id),
                              get_space_heat_cons_key(agent_id),
                              get_hot_tap_water_cons_key(agent_id)] for agent_id in agent_specs.values()]

        with (mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.create_job_if_new_config',
                         return_value='fake_job_id'),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.read_config',
                         return_value=fake_config),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.get_all_agents_in_config',
                         return_value=agent_specs),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.get_generated_mock_data',
                         return_value=pd.DataFrame(columns=[bid for sublist in mock_data_columns for bid in sublist]))):
            with self.assertRaises(RuntimeError):
                simulator = TradingSimulator('fake_config')
                simulator.initialize_data()
                simulator.initialize_agents()

    def test_get_quantity_heating_sold_by_external_grid(self):
        """Test that get_quantity_heating_sold_by_external_grid doesn't break when there are no external trades."""
        self.assertEqual(0, get_quantity_heating_sold_by_external_grid([]))

    def test_get_external_heating_prices_from_empty_data_store(self):
        """
        When trying to calculate external heating prices using an empty DataStore, NaNs should be returned for exact
        prices, and warnings should be logged.
        """
        with self.assertLogs() as captured:
            heating_price_lst = get_external_heating_prices(self.heat_pricing,
                                                            pd.DatetimeIndex([datetime.datetime(2019, 2, 1),
                                                                              datetime.datetime(2019, 2, 2)]))
        heating_prices = pd.DataFrame.from_records(heating_price_lst)
        self.assertTrue(len(captured.records) > 0)
        log_levels_captured = [rec.levelname for rec in captured.records]
        self.assertTrue('WARNING' in log_levels_captured)
        entry = heating_prices[(heating_prices.year == 2019) & (heating_prices.month == 2)].iloc[0]
        self.assertTrue(np.isnan(entry.exact_retail_price))
        self.assertTrue(np.isnan(entry.exact_wholesale_price))
        self.assertFalse(np.isnan(entry.estimated_retail_price))
        self.assertFalse(np.isnan(entry.estimated_wholesale_price))

    def test_construct_df_from_datetime_dict(self):
        """
        Test construct_df_from_datetime_dict method, by creating a Dict[datetime, Trade]
        """
        dts = hourly_datetime_array_between(datetime.datetime(2019, 1, 1), datetime.datetime(2020, 1, 1))
        dt_dict = {dt: [Trade(Action.BUY, Resource.ELECTRICITY, i, i, 'Agent' + str(i), False, Market.LOCAL, dt)
                        for i in range(1, 6)]
                   for dt in dts}
        my_df = construct_df_from_datetime_dict(dt_dict)
        self.assertEqual(8761 * 5, len(my_df.index))
