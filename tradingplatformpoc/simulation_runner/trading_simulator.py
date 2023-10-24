import datetime
import logging
import math
import threading
from typing import Any, Dict, List, Tuple

import pandas as pd

from tradingplatformpoc.agent.battery_agent import BatteryAgent
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.app.app_threading import StoppableThread
from tradingplatformpoc.database import bulk_insert
from tradingplatformpoc.digitaltwin.battery import Battery
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.generate_data.generate_mock_data import get_generated_mock_data
from tradingplatformpoc.generate_data.mock_data_utils import get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.market import balance_manager
from tradingplatformpoc.market import market_solver
from tradingplatformpoc.market.balance_manager import correct_for_exact_heating_price
from tradingplatformpoc.market.bid import GrossBid, Resource
from tradingplatformpoc.market.trade import TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.simulation_runner.simulation_utils import get_external_heating_prices, \
    get_quantity_heating_sold_by_external_grid, go_through_trades_metadata, \
    net_bids_from_gross_bids
from tradingplatformpoc.sql.bid.crud import bids_to_db_dict
from tradingplatformpoc.sql.bid.models import Bid as TableBid
from tradingplatformpoc.sql.clearing_price.crud import clearing_prices_to_db_dict
from tradingplatformpoc.sql.clearing_price.models import ClearingPrice as TableClearingPrice
from tradingplatformpoc.sql.config.crud import get_all_agents_in_config, read_config
from tradingplatformpoc.sql.electricity_price.models import ElectricityPrice as TableElectricityPrice
from tradingplatformpoc.sql.extra_cost.crud import extra_costs_to_db_dict
from tradingplatformpoc.sql.extra_cost.models import ExtraCost as TableExtraCost
from tradingplatformpoc.sql.heating_price.models import HeatingPrice as TableHeatingPrice
from tradingplatformpoc.sql.input_data.crud import get_periods_from_db, read_inputs_df_for_agent_creation
from tradingplatformpoc.sql.input_electricity_price.crud import electricity_price_df_from_db
from tradingplatformpoc.sql.job.crud import delete_job, get_config_id_for_job_id, \
    update_job_with_time
from tradingplatformpoc.sql.level.crud import levels_to_db_dict
from tradingplatformpoc.sql.level.models import Level as TableLevel
from tradingplatformpoc.sql.trade.crud import trades_to_db_dict
from tradingplatformpoc.sql.trade.models import Trade as TableTrade
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod, flatten_collection

logger = logging.getLogger(__name__)


class TradingSimulator:
    def __init__(self, job_id: str):
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
        self.config_data = self.config_data

        self.use_local_market = self.config_data['General']['LocalMarket']

        self.heat_pricing: HeatingPrice = HeatingPrice(
            heating_wholesale_price_fraction=self.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'],
            heat_transfer_loss=self.config_data['AreaInfo']["HeatTransferLoss"])
        self.electricity_pricing: ElectricityPrice = ElectricityPrice(
            elec_wholesale_offset=self.config_data['AreaInfo']['ExternalElectricityWholesalePriceOffset'],
            elec_tax=self.config_data['AreaInfo']["ElectricityTax"],
            elec_grid_fee=self.config_data['AreaInfo']["ElectricityGridFee"],
            elec_tax_internal=self.config_data['AreaInfo']["ElectricityTaxInternal"],
            elec_grid_fee_internal=self.config_data['AreaInfo']["ElectricityGridFeeInternal"],
            nordpool_data=electricity_price_df_from_db())

        self.trading_periods = get_periods_from_db().sort_values()

        self.clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]] = {}
        self.storage_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}
        self.heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}

    def initialize_agents(self) -> Tuple[List[IAgent], List[GridAgent]]:
        # Register all agents
        # Keep a list of all agents to iterate over later
        agents: List[IAgent] = []
        grid_agents: List[GridAgent] = []

        # Read input data (irradiation and grocery store consumption) from database
        inputs_df = read_inputs_df_for_agent_creation()
        # Get mock data
        buildings_mock_data: pd.DataFrame = get_generated_mock_data(self.config_id)

        for agent in self.config_data["Agents"]:
            agent_type = agent["Type"]
            agent_name = agent['Name']

            if agent_type in ["BuildingAgent", "PVAgent", "GroceryStoreAgent"]:
                pv_prod_series = calculate_solar_prod(inputs_df['irradiation'],
                                                      agent['PVArea'],
                                                      agent['PVEfficiency'])
            if agent_type == "BuildingAgent":
                agent_id = self.agent_specs[agent['Name']]
                elec_cons_series = buildings_mock_data[get_elec_cons_key(agent_id)]
                space_heat_cons_series = buildings_mock_data[get_space_heat_cons_key(agent_id)]
                hot_tap_water_cons_series = buildings_mock_data[get_hot_tap_water_cons_key(agent_id)]

                building_digital_twin = StaticDigitalTwin(electricity_usage=elec_cons_series,
                                                          space_heating_usage=space_heat_cons_series,
                                                          hot_water_usage=hot_tap_water_cons_series,
                                                          electricity_production=pv_prod_series)

                agents.append(BuildingAgent(heat_pricing=self.heat_pricing,
                                            electricity_pricing=self.electricity_pricing,
                                            digital_twin=building_digital_twin,
                                            guid=agent_name, nbr_heat_pumps=agent["NumberHeatPumps"],
                                            coeff_of_perf=agent["COP"]))

            elif agent_type == "BatteryAgent":
                storage_digital_twin = Battery(max_capacity_kwh=agent["Capacity"],
                                               max_charge_rate_fraction=agent["ChargeRate"],
                                               max_discharge_rate_fraction=agent["DischargeRate"],
                                               discharging_efficiency=agent["RoundTripEfficiency"])
                agents.append(BatteryAgent(self.electricity_pricing, storage_digital_twin,
                                           n_hours_to_look_back=agent["NHoursBack"],
                                           buy_price_percentile=agent["BuyPricePercentile"],
                                           sell_price_percentile=agent["SellPricePercentile"],
                                           guid=agent_name))
            elif agent_type == "PVAgent":
                pv_digital_twin = StaticDigitalTwin(electricity_production=pv_prod_series)
                agents.append(PVAgent(self.electricity_pricing, pv_digital_twin, guid=agent_name))
            elif agent_type == "GroceryStoreAgent":
                grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=inputs_df['coop_electricity_consumed'],
                                                               space_heating_usage=inputs_df['coop_heating_consumed'],
                                                               # TODO: Grocery store tap water consumption
                                                               electricity_production=pv_prod_series)
                agents.append(BuildingAgent(heat_pricing=self.heat_pricing,
                                            electricity_pricing=self.electricity_pricing,
                                            digital_twin=grocery_store_digital_twin,
                                            guid=agent_name))
            elif agent_type == "GridAgent":
                if Resource[agent["Resource"]] == Resource.ELECTRICITY:
                    grid_agent = GridAgent(self.electricity_pricing, Resource[agent["Resource"]],
                                           max_transfer_per_hour=agent["TransferRate"], guid=agent_name)
                elif Resource[agent["Resource"]] == Resource.HEATING:
                    grid_agent = GridAgent(self.heat_pricing, Resource[agent["Resource"]],
                                           max_transfer_per_hour=agent["TransferRate"], guid=agent_name)
                agents.append(grid_agent)
                grid_agents.append(grid_agent)

        # Verify that we have a Grid Agent
        if not any(isinstance(agent, GridAgent) for agent in agents):
            raise RuntimeError("No grid agent initialized")

        return agents, grid_agents

    def run(self, number_of_batches: int = 5):
        """
        The core loop of the simulation, running through the desired time period and performing trades.
        """

        logger.info("Starting trading simulations")

        number_of_trading_periods = len(self.trading_periods)
        batch_size = math.ceil(number_of_trading_periods / number_of_batches)
        
        # Loop over batches
        for batch_number in range(number_of_batches):
            current_thread = threading.current_thread()
            if isinstance(current_thread, StoppableThread):
                if current_thread.is_stopped():
                    logger.error('Simulation stopped by event.')
                    raise Exception("Simulation stopped by event.")
            logger.info("Simulating batch number {} of {}".format(batch_number + 1, number_of_batches))

            # Periods in batch
            trading_periods_in_this_batch = self.trading_periods[
                batch_number * batch_size:min((batch_number + 1) * batch_size, number_of_trading_periods)]

            all_bids_list_batch: List[TableBid] = []
            all_trades_list_batch: List[TableTrade] = []
            all_extra_costs_batch: List[TableExtraCost] = []
            electricity_price_list_batch: List[TableElectricityPrice] = []

            # Loop over periods i batch
            for period in trading_periods_in_this_batch:
                if period.day == period.hour == 1:
                    info_string = "Simulations entering {:%B}".format(period)
                    logger.info(info_string)

                # TODO: Skipp bidding if self.use_local_market and go straight to trades
                # Get all bids
                bids = [agent.make_bids(period, self.clearing_prices_historical) for agent in self.agents]

                # Flatten bids list
                bids_flat: List[GrossBid] = flatten_collection(bids)

                # Add in tax and grid fee for SELL bids (for electricity, heating is not taxed)
                net_bids = net_bids_from_gross_bids(bids_flat, self.electricity_pricing)

                # Resolve bids
                clearing_prices, bids_with_acceptance_status = market_solver.resolve_bids(period, net_bids)
                self.clearing_prices_historical[period] = clearing_prices

                all_bids_list_batch.append(bids_with_acceptance_status)

                # Send clearing price back to agents, allow them to "make trades", i.e. decide if they want to buy/sell
                # energy, from/to either the local market or directly from/to the external grid.
                # To be clear: These "trades" are for _actual_ amounts, not predicted.
                # All agents except the external grid agent
                # makes these, then finally the external grid agent "fills in" the energy
                # imbalances through "trades" of its own
                trades_excl_external = []
                for agent in self.agents:
                    accepted_bids_for_agent = [bid for bid in bids_with_acceptance_status
                                               if bid.source == agent.guid and bid.accepted_quantity > 0]
                    trades, metadata = agent.make_trades_given_clearing_price(period, clearing_prices,
                                                                              accepted_bids_for_agent)
                    trades_excl_external.extend(trades)
                    go_through_trades_metadata(metadata, period, agent.guid, self.heat_pump_levels_dict,
                                               self.storage_levels_dict)

                trades_excl_external = [i for i in trades_excl_external if i]  # filter out None
                external_trades = flatten_collection([ga.calculate_external_trades(trades_excl_external,
                                                                                   clearing_prices)
                                                      for ga in self.grid_agents])
                all_trades_for_period = trades_excl_external + external_trades
                all_trades_list_batch.append(all_trades_for_period)

                external_heating_sell_quantity = get_quantity_heating_sold_by_external_grid(external_trades)
                self.heat_pricing.add_external_heating_sell(period, external_heating_sell_quantity)

                wholesale_price_elec = self.electricity_pricing.get_exact_wholesale_price(period)
                retail_price_elec = self.electricity_pricing.get_exact_retail_price(period, include_tax=True)
                wholesale_prices = {Resource.ELECTRICITY: wholesale_price_elec,
                                    Resource.HEATING: self.heat_pricing.get_estimated_wholesale_price(period)}
                extra_costs = balance_manager.calculate_penalty_costs_for_period(bids_with_acceptance_status,
                                                                                 all_trades_for_period,
                                                                                 period,
                                                                                 clearing_prices,
                                                                                 wholesale_prices)

                electricity_price_list_batch.append({
                    'job_id': self.job_id, 'period': period, 'retail_price': retail_price_elec,
                    'wholesale_price': wholesale_price_elec})

                all_extra_costs_batch.extend(extra_costs)

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

        clearing_prices_dicts = clearing_prices_to_db_dict(self.clearing_prices_historical, self.job_id)
        heat_pump_level_dicts = levels_to_db_dict(self.heat_pump_levels_dict,
                                                  TradeMetadataKey.HEAT_PUMP_WORKLOAD.name, self.job_id)
        storage_level_dicts = levels_to_db_dict(self.storage_levels_dict,
                                                TradeMetadataKey.STORAGE_LEVEL.name, self.job_id)
        bulk_insert(TableClearingPrice, clearing_prices_dicts)
        bulk_insert(TableLevel, heat_pump_level_dicts)
        bulk_insert(TableLevel, storage_level_dicts)

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
