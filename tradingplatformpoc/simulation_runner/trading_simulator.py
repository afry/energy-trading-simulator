import datetime
import logging
import math
import threading
from typing import Any, Dict, List, Tuple

import pandas as pd

from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.app.app_threading import StoppableThread
from tradingplatformpoc.constants import LEC_CAN_SELL_HEAT_TO_EXTERNAL
from tradingplatformpoc.database import bulk_insert
from tradingplatformpoc.digitaltwin.battery import Battery
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.generate_data.generate_mock_data import get_generated_mock_data
from tradingplatformpoc.generate_data.mock_data_utils import get_cooling_cons_key, get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.market.balance_manager import correct_for_exact_heating_price
from tradingplatformpoc.market.bid import NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.extra_cost import ExtraCost
from tradingplatformpoc.market.trade import Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.simulation_runner.chalmers_interface import optimize
from tradingplatformpoc.simulation_runner.results_calculator import calculate_results_and_save
from tradingplatformpoc.simulation_runner.simulation_utils import get_external_heating_prices
from tradingplatformpoc.sql.bid.crud import bids_to_db_dict
from tradingplatformpoc.sql.bid.models import Bid as TableBid
from tradingplatformpoc.sql.config.crud import get_all_agents_in_config, read_config
from tradingplatformpoc.sql.electricity_price.models import ElectricityPrice as TableElectricityPrice
from tradingplatformpoc.sql.extra_cost.crud import extra_costs_to_db_dict
from tradingplatformpoc.sql.extra_cost.models import ExtraCost as TableExtraCost
from tradingplatformpoc.sql.heating_price.models import HeatingPrice as TableHeatingPrice
from tradingplatformpoc.sql.input_data.crud import get_periods_from_db, read_inputs_df_for_agent_creation
from tradingplatformpoc.sql.input_electricity_price.crud import electricity_price_series_from_db
from tradingplatformpoc.sql.job.crud import delete_job, get_config_id_for_job_id, \
    update_job_with_time
from tradingplatformpoc.sql.level.crud import levels_to_db_dict
from tradingplatformpoc.sql.level.models import Level as TableLevel
from tradingplatformpoc.sql.trade.crud import trades_to_db_dict
from tradingplatformpoc.sql.trade.models import Trade as TableTrade
from tradingplatformpoc.trading_platform_utils import add_all_to_nested_dict, calculate_solar_prod, get_glpk_solver


logger = logging.getLogger(__name__)


class TradingSimulator:
    def __init__(self, job_id: str):
        self.solver = get_glpk_solver()
        self.job_id = job_id
        self.config_id = get_config_id_for_job_id(self.job_id)
        self.config_data: Dict[str, Any] = read_config(self.config_id)
        self.agent_specs = get_all_agents_in_config(self.config_id)

    def __call__(self):
        if (self.job_id is not None) and (self.config_data is not None):
            try:
                update_job_with_time(self.job_id, 'start_time')
                self.initialize_data()
                self.agents, self.grid_agents = self.initialize_agents()
                self.run()
                self.extract_heating_price()
                update_job_with_time(self.job_id, 'end_time')

            except Exception as e:
                logger.exception(e)
                delete_job(self.job_id)

    def initialize_data(self):
        self.local_market_enabled = self.config_data['AreaInfo']['LocalMarketEnabled']

        self.heat_pricing: HeatingPrice = HeatingPrice(
            heating_wholesale_price_fraction=self.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'],
            heat_transfer_loss=self.config_data['AreaInfo']["HeatTransferLoss"])
        self.electricity_pricing: ElectricityPrice = ElectricityPrice(
            elec_wholesale_offset=self.config_data['AreaInfo']['ExternalElectricityWholesalePriceOffset'],
            elec_tax=self.config_data['AreaInfo']["ElectricityTax"],
            elec_grid_fee=self.config_data['AreaInfo']["ElectricityGridFee"],
            elec_tax_internal=self.config_data['AreaInfo']["ElectricityTaxInternal"],
            elec_grid_fee_internal=self.config_data['AreaInfo']["ElectricityGridFeeInternal"],
            nordpool_data=electricity_price_series_from_db())

        self.trading_periods = get_periods_from_db().sort_values()
        self.trading_periods = self.trading_periods.take(list(range(48)) + list(range(4008, 4056)))  # FIXME: Remove
        self.trading_horizon = self.config_data['AreaInfo']['TradingHorizon']

    def initialize_agents(self) -> Tuple[List[IAgent], Dict[Resource, GridAgent]]:
        # Register all agents
        # Keep a list of all agents to iterate over later
        agents: List[IAgent] = []
        grid_agents: Dict[Resource, GridAgent] = {}

        # Read input data (irradiation and grocery store consumption) from database
        inputs_df = read_inputs_df_for_agent_creation()
        # Get mock data
        blocks_mock_data: pd.DataFrame = get_generated_mock_data(self.config_id)
        area_info = self.config_data['AreaInfo']

        for agent in self.config_data["Agents"]:
            agent_type = agent["Type"]
            agent_name = agent['Name']

            # Note - when making changes to StaticDigitalTwin creation here, you may also need to change the
            # "reconstruct_static_digital_twin"-related methods in app_data_display.py

            if agent_type == "BlockAgent":
                agent_id = self.agent_specs[agent['Name']]
                elec_cons_series = blocks_mock_data.get(get_elec_cons_key(agent_id))
                space_heat_cons_series = blocks_mock_data.get(get_space_heat_cons_key(agent_id))
                hot_tap_water_cons_series = blocks_mock_data.get(get_hot_tap_water_cons_key(agent_id))
                cool_cons_series = blocks_mock_data.get(get_cooling_cons_key(agent_id))
                pv_prod_series = calculate_solar_prod(inputs_df['irradiation'],
                                                      agent['PVArea'],
                                                      area_info['PVEfficiency'])

                block_digital_twin = StaticDigitalTwin(gross_floor_area=agent['GrossFloorArea'],
                                                       electricity_usage=elec_cons_series,
                                                       space_heating_usage=space_heat_cons_series,
                                                       hot_water_usage=hot_tap_water_cons_series,
                                                       cooling_usage=cool_cons_series,
                                                       electricity_production=pv_prod_series)

                storage_digital_twin = Battery(max_capacity_kwh=agent["BatteryCapacity"],
                                               max_charge_rate_fraction=area_info["BatteryChargeRate"],
                                               max_discharge_rate_fraction=area_info["BatteryDischargeRate"],
                                               discharging_efficiency=area_info["BatteryEfficiency"])

                agents.append(
                    BlockAgent(self.local_market_enabled, heat_pricing=self.heat_pricing,
                               electricity_pricing=self.electricity_pricing, digital_twin=block_digital_twin,
                               can_sell_heat_to_external=LEC_CAN_SELL_HEAT_TO_EXTERNAL,
                               heat_pump_max_input=agent["HeatPumpMaxInput"],
                               heat_pump_max_output=agent["HeatPumpMaxOutput"],
                               booster_pump_max_input=agent["BoosterPumpMaxInput"],
                               booster_pump_max_output=agent["BoosterPumpMaxOutput"],
                               acc_tank_volume=agent["AccumulatorTankVolume"],
                               battery=storage_digital_twin,
                               guid=agent_name))

            elif agent_type == "GroceryStoreAgent":
                pv_prod_series = calculate_solar_prod(inputs_df['irradiation'],
                                                      agent['PVArea'],
                                                      agent['PVEfficiency'])
                space_heat_prod = inputs_df['coop_space_heating_produced'] if agent["SellExcessHeat"] else None
                grocery_store_digital_twin = StaticDigitalTwin(gross_floor_area=agent['GrossFloorArea'],
                                                               electricity_usage=inputs_df['coop_electricity_consumed'],
                                                               space_heating_usage=inputs_df[
                                                                   'coop_space_heating_consumed'],
                                                               hot_water_usage=inputs_df['coop_hot_tap_water_consumed'],
                                                               electricity_production=pv_prod_series,
                                                               space_heating_production=space_heat_prod)
                agents.append(
                    BlockAgent(self.local_market_enabled, heat_pricing=self.heat_pricing,
                               electricity_pricing=self.electricity_pricing, digital_twin=grocery_store_digital_twin,
                               can_sell_heat_to_external=LEC_CAN_SELL_HEAT_TO_EXTERNAL,
                               heat_pump_max_input=agent["HeatPumpMaxInput"],
                               heat_pump_max_output=agent["HeatPumpMaxOutput"],
                               booster_pump_max_input=agent["BoosterPumpMaxInput"],
                               booster_pump_max_output=agent["BoosterPumpMaxOutput"],
                               acc_tank_volume=agent["AccumulatorTankVolume"],
                               guid=agent_name))
            elif agent_type == "GridAgent":
                if Resource[agent["Resource"]] == Resource.ELECTRICITY:
                    grid_agent = GridAgent(self.local_market_enabled, self.electricity_pricing,
                                           Resource[agent["Resource"]], can_buy=True,
                                           max_transfer_per_hour=agent["TransferRate"], guid=agent_name)
                elif Resource[agent["Resource"]] == Resource.HEATING:
                    grid_agent = GridAgent(self.local_market_enabled, self.heat_pricing, Resource[agent["Resource"]],
                                           can_buy=LEC_CAN_SELL_HEAT_TO_EXTERNAL,
                                           max_transfer_per_hour=agent["TransferRate"], guid=agent_name)
                agents.append(grid_agent)
                grid_agents[Resource[agent["Resource"]]] = grid_agent

        # Verify that we have a Grid Agent
        if not any(isinstance(agent, GridAgent) for agent in agents):
            raise RuntimeError("No grid agent initialized")

        return agents, grid_agents

    def run(self, number_of_batches: int = 5):
        """
        The core loop of the simulation, running through the desired time period and performing trades.
        """

        logger.info("Starting trading simulations")

        # clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]] = {}
        battery_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}
        hp_high_prod: Dict[str, Dict[datetime.datetime, float]] = {}
        hp_low_prod: Dict[str, Dict[datetime.datetime, float]] = {}

        number_of_trading_horizons = int(len(self.trading_periods) // self.trading_horizon)
        logger.info('Will run {} trading horizons'.format(number_of_trading_horizons))
        new_batch_size = math.ceil(number_of_trading_horizons / number_of_batches)

        # Loop over batches
        for batch_number in range(number_of_batches):
            current_thread = threading.current_thread()
            if isinstance(current_thread, StoppableThread):
                if current_thread.is_stopped():
                    logger.error('Simulation stopped by event.')
                    raise Exception("Simulation stopped by event.")
            logger.info("Simulating batch number {} of {}".format(batch_number + 1, number_of_batches))

            # Horizons in batch
            trading_horizon_start_points = self.trading_periods[::self.trading_horizon]
            thsps_in_this_batch = trading_horizon_start_points[
                batch_number * new_batch_size:min((batch_number + 1) * new_batch_size, number_of_trading_horizons)]
            all_bids_list_batch: List[List[NetBidWithAcceptanceStatus]] = []
            all_trades_list_batch: List[List[Trade]] = []
            all_extra_costs_batch: List[ExtraCost] = []
            electricity_price_list_batch: List[dict] = []

            # ------- NEW --------
            for horizon_start in thsps_in_this_batch:
                logger.info("Simulating {:%Y-%m-%d}".format(horizon_start))
                # if horizon_start.day == horizon_start.hour == 1:
                #     info_string = "Simulations entering {:%B}".format(horizon_start)
                #     logger.info(info_string)
                # for i in range(10, len(self.agents) - len(self.grid_agents.keys())):
                #     print('Adding ' + self.agents[i-1].guid)
                #     chalmers_outputs = optimize(self.solver, self.agents[:i], self.grid_agents,
                #                                 self.config_data['AreaInfo'], horizon_start,
                #                                 self.electricity_pricing, self.heat_pricing)
                chalmers_outputs = optimize(self.solver, self.agents, self.grid_agents, self.config_data['AreaInfo'],
                                            horizon_start, self.electricity_pricing, self.heat_pricing)
                all_trades_list_batch.append(chalmers_outputs.trades)
                add_all_to_nested_dict(battery_levels_dict, chalmers_outputs.battery_storage_levels)
                add_all_to_nested_dict(hp_high_prod, chalmers_outputs.hp_high_prod)
                add_all_to_nested_dict(hp_low_prod, chalmers_outputs.hp_low_prod)

            # # ------- OLD --------
            # for period in trading_periods_in_this_batch:
            #     if period.day == period.hour == 1:
            #         info_string = "Simulations entering {:%B}".format(period)
            #         logger.info(info_string)
            #
            #     if self.local_market_enabled:
            #         # Get all bids
            #         bids = [agent.make_bids(period, self.clearing_prices_historical) for agent in self.agents]
            #
            #         # Flatten bids list
            #         bids_flat: List[GrossBid] = flatten_collection(bids)
            #
            #         # Add in tax and grid fee for SELL bids (for electricity, heating is not taxed)
            #         net_bids = net_bids_from_gross_bids(bids_flat, self.electricity_pricing)
            #
            #         # Resolve bids
            #         clearing_prices, bids_with_acceptance_status = market_solver.resolve_bids(period, net_bids)
            #         self.clearing_prices_historical[period] = clearing_prices
            #
            #         all_bids_list_batch.append(bids_with_acceptance_status)
            #     else:
            #         clearing_prices, bids_with_acceptance_status = market_solver.without_local_market()
            #
            #     # Send clearing price back to agents, allow them to "make trades", i.e. decide if they want to
            #     # buy/sell energy, from/to either the local market or directly from/to the external grid.
            #     # To be clear: These "trades" are for _actual_ amounts, not predicted.
            #     # All agents except the external grid agent
            #     # makes these, then finally the external grid agent "fills in" the energy
            #     # imbalances through "trades" of its own
            #     trades_excl_external = []
            #     for agent in self.agents:
            #         accepted_bids_for_agent = [bid for bid in bids_with_acceptance_status
            #                                    if bid.source == agent.guid and bid.accepted_quantity > 0]
            #         trades, metadata = agent.make_trades_given_clearing_price(period, clearing_prices,
            #                                                                   accepted_bids_for_agent)
            #         trades_excl_external.extend(trades)
            #         go_through_trades_metadata(metadata, period, agent.guid, self.heat_pump_levels_dict,
            #                                    self.storage_levels_dict)
            #
            #     trades_excl_external = [i for i in trades_excl_external if i]  # filter out None
            #     external_trades = flatten_collection([ga.calculate_external_trades(trades_excl_external,
            #                                                                        clearing_prices)
            #                                           for ga in self.grid_agents.values()])
            #     all_trades_for_period = trades_excl_external + external_trades
            #     all_trades_list_batch.append(all_trades_for_period)
            #
            #     external_heating_sell_quantity = get_quantity_heating_sold_by_external_grid(external_trades)
            #     self.heat_pricing.add_external_heating_sell(period, external_heating_sell_quantity)
            #
            #     wholesale_price_elec = self.electricity_pricing.get_exact_wholesale_price(period)
            #     retail_price_elec = self.electricity_pricing.get_exact_retail_price(period, include_tax=True)
            #     wholesale_prices = {Resource.ELECTRICITY: wholesale_price_elec,
            #                         Resource.HEATING: self.heat_pricing.get_estimated_wholesale_price(period)}
            #     extra_costs = balance_manager.calculate_penalty_costs_for_period(bids_with_acceptance_status,
            #                                                                      all_trades_for_period,
            #                                                                      period,
            #                                                                      clearing_prices,
            #                                                                      wholesale_prices,
            #                                                                      self.local_market_enabled)
            #
            #     electricity_price_list_batch.append({
            #         'job_id': self.job_id, 'period': period, 'retail_price': retail_price_elec,
            #         'wholesale_price': wholesale_price_elec})
            #
            #     all_extra_costs_batch.extend(extra_costs)

            logger.info('Saving bids to db...')
            bid_dict = bids_to_db_dict(all_bids_list_batch, self.job_id)
            bulk_insert(TableBid, bid_dict)
            logger.info('Saving trades to db...')
            trade_dict = trades_to_db_dict(all_trades_list_batch, self.job_id)
            bulk_insert(TableTrade, trade_dict)
            logger.info('Saving extra costs to db...')
            extra_cost_dict = extra_costs_to_db_dict(all_extra_costs_batch, self.job_id)
            bulk_insert(TableExtraCost, extra_cost_dict)
            logger.info('Saving electricity price to db...')
            bulk_insert(TableElectricityPrice, electricity_price_list_batch)

        # clearing_prices_dicts = clearing_prices_to_db_dict(clearing_prices_historical, self.job_id)
        battery_level_dicts = levels_to_db_dict(battery_levels_dict, TradeMetadataKey.BATTERY_LEVEL.name, self.job_id)
        hp_high_prod_dicts = levels_to_db_dict(hp_high_prod, TradeMetadataKey.HP_HIGH_HEAT_PROD.name, self.job_id)
        hp_low_prod_dicts = levels_to_db_dict(hp_low_prod, TradeMetadataKey.HP_LOW_HEAT_PROD.name, self.job_id)
        # bulk_insert(TableClearingPrice, clearing_prices_dicts)
        bulk_insert(TableLevel, battery_level_dicts)
        bulk_insert(TableLevel, hp_high_prod_dicts)
        bulk_insert(TableLevel, hp_low_prod_dicts)

        calculate_results_and_save(self.job_id, self.agents, self.grid_agents,
                                   high_heat_prod=sum(sum(subdict.values()) for subdict in hp_high_prod.values()),
                                   low_heat_prod=sum(sum(subdict.values()) for subdict in hp_low_prod.values()))

        logger.info("Finished simulating trades, beginning calculations on district heating price...")

    def extract_heating_price(self):
        """
        Simulations finished. Now, we need to go through and calculate the exact district heating price for each month
        """
        logger.info('Calculating external_heating_prices')
        heating_price_list = get_external_heating_prices(self.heat_pricing, self.job_id,
                                                         self.trading_periods)
        bulk_insert(TableHeatingPrice, heating_price_list)

        logger.info('Calculating heat_cost_discrepancy_corrections')
        heating_prices = pd.DataFrame.from_records(heating_price_list)
        heat_cost_discrepancy_corrections = correct_for_exact_heating_price(self.trading_periods,
                                                                            heating_prices,
                                                                            self.job_id)
        logger.info('Saving extra costs to db...')
        extra_cost_dict = extra_costs_to_db_dict(heat_cost_discrepancy_corrections, self.job_id)
        bulk_insert(TableExtraCost, extra_cost_dict)

        logger.info('Simulation finished!')
