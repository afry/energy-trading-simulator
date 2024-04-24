import datetime
from unittest import TestCase, mock

import numpy as np

import pandas as pd

import pytz

from tradingplatformpoc.config.access_config import read_config
from tradingplatformpoc.data.preprocessing import read_and_process_input_data
from tradingplatformpoc.generate_data.mock_data_utils import get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator
from tradingplatformpoc.sql.job.models import uuid_as_str_generator
from tradingplatformpoc.trading_platform_utils import get_external_heating_prices


class Test(TestCase):

    fake_job_id = "111111111111"
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
                       if agent['Type'] == 'BlockAgent'}
        mock_data_columns = [[get_elec_cons_key(agent_id),
                              get_space_heat_cons_key(agent_id),
                              get_hot_tap_water_cons_key(agent_id)] for agent_id in agent_specs.values()]
        input_data = read_and_process_input_data()[[
            'datetime', 'irradiation', 'coop_electricity_consumed', 'coop_hot_tap_water_consumed',
            'coop_space_heating_consumed', 'coop_space_heating_produced']].rename(columns={'datetime': 'period'})

        with (mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.get_config_id_for_job_id',
                         return_value='fake_config_id'),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.read_config',
                         return_value=fake_config),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.get_all_agent_name_id_pairs_in_config',
                         return_value=agent_specs),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.get_periods_from_db',
                         return_value=pd.DatetimeIndex(input_data.period)),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.get_generated_mock_data',
                         return_value=pd.DataFrame(columns=[bid for sublist in mock_data_columns for bid in sublist])),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.read_inputs_df_for_agent_creation',
                         return_value=input_data)):
            with self.assertRaises(RuntimeError):
                simulator = TradingSimulator('fake_job_id')
                simulator.initialize_data()
                simulator.initialize_agents()

    def test_get_external_heating_prices_from_empty_data_store(self):
        """
        When trying to calculate external heating prices using an empty DataStore, NaNs should be returned for exact
        prices, and warnings should be logged.
        """
        with self.assertLogs() as captured:
            heating_price_list = get_external_heating_prices(self.heat_pricing, self.fake_job_id,
                                                             pd.DatetimeIndex([datetime.datetime(2019, 2, 1),
                                                                              datetime.datetime(2019, 2, 2)]))
        heating_prices = pd.DataFrame.from_records(heating_price_list)
        self.assertTrue(len(captured.records) > 0)
        log_levels_captured = [rec.levelname for rec in captured.records]
        self.assertTrue('WARNING' in log_levels_captured)
        entry = heating_prices[(heating_prices.year == 2019) & (heating_prices.month == 2)].iloc[0]
        self.assertTrue(np.isnan(entry.exact_retail_price))
        self.assertTrue(np.isnan(entry.exact_wholesale_price))
        self.assertFalse(np.isnan(entry.estimated_retail_price))
        self.assertFalse(np.isnan(entry.estimated_wholesale_price))

    def test_something(self):
        """Test that an error is thrown if no GridAgents are initialized."""
        fake_config = {'Agents': [agent for agent in self.config['Agents'] if agent['Type'] != 'GridAgent'],
                       'AreaInfo': self.config['AreaInfo'],
                       'MockDataConstants': self.config['MockDataConstants']}
        fake_config['AreaInfo']['ElectricityPriceYear'] = 2022
        input_data = read_and_process_input_data()[[
            'datetime', 'irradiation', 'coop_electricity_consumed', 'coop_hot_tap_water_consumed',
            'coop_space_heating_consumed', 'coop_space_heating_produced']].rename(columns={'datetime': 'period'})

        with (mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.get_config_id_for_job_id',
                         return_value='fake_config_id'),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.read_config',
                         return_value=fake_config),
              mock.patch('tradingplatformpoc.simulation_runner.trading_simulator.get_periods_from_db',
                         return_value=pd.DatetimeIndex(input_data.period))):
            simulator = TradingSimulator('fake_job_id')
            simulator.initialize_data()

            dt = datetime.datetime(2019, 2, 1, 0, tzinfo=pytz.UTC)
            # 0.792575955 is the value for 2022-02-04 01:00 CET (3 day offset to make weekdays match)
            self.assertAlmostEqual(simulator.electricity_pricing.get_nordpool_price_for_periods(dt), 0.792575955)
