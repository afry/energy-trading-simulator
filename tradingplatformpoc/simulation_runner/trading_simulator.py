import datetime
import gc
import logging
import math
import threading
from typing import Any, Collection, Dict, List, Tuple

import pandas as pd

from tradingplatformpoc.agent.battery_agent import BatteryAgent
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.app.app_threading import StoppableThread
from tradingplatformpoc.data.preproccessing import read_energy_data, read_irradiation_data, read_nordpool_data
from tradingplatformpoc.database import bulk_insert
from tradingplatformpoc.digitaltwin.battery import Battery
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.generate_data.generate_mock_data import get_generated_mock_data
from tradingplatformpoc.generate_data.mock_data_generation_functions import get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.market import balance_manager
from tradingplatformpoc.market import market_solver
from tradingplatformpoc.market.balance_manager import correct_for_exact_heating_price
from tradingplatformpoc.market.bid import GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.extra_cost import ExtraCost
from tradingplatformpoc.market.trade import Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.simulation_runner.simulation_utils import get_external_heating_prices, \
    get_quantity_heating_sold_by_external_grid, go_through_trades_metadata, \
    net_bids_from_gross_bids
from tradingplatformpoc.sql.bid.crud import bids_to_db_objects
from tradingplatformpoc.sql.clearing_price.crud import clearing_prices_to_db_objects
from tradingplatformpoc.sql.config.crud import get_all_agents_in_config, read_config
from tradingplatformpoc.sql.electricity_price.models import ElectricityPrice as TableElectricityPrice
from tradingplatformpoc.sql.extra_cost.crud import extra_costs_to_db_objects
from tradingplatformpoc.sql.heating_price.crud import external_heating_prices_to_db_objects
from tradingplatformpoc.sql.job.crud import create_job_if_new_config, delete_job, update_job_with_end_time
from tradingplatformpoc.sql.level.crud import levels_to_db_objects
from tradingplatformpoc.sql.trade.crud import trades_to_db_objects
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod, flatten_collection, \
    get_intersection


logger = logging.getLogger(__name__)


class TradingSimulator:
    def __init__(self, config_id: str):
        self.config_id = config_id
        self.job_id = create_job_if_new_config(config_id)
        self.config_data: Dict[str, Any] = read_config(config_id)
        self.agent_specs = get_all_agents_in_config(self.config_id)

    def __call__(self):
        if (self.job_id is not None) and (self.config_data is not None):
            try:

                self.initialize_data()
                self.agents, self.grid_agents = self.initialize_agents()
                self.run()
                results = self.extract_results()
                update_job_with_end_time(self.job_id)
                return results

            except Exception as e:
                logger.exception(e)
                delete_job(self.job_id)
                return None
        else:
            return None

    def initialize_data(self):
        self.config_data = self.config_data

        external_price_data = read_nordpool_data()
        self.heat_pricing: HeatingPrice = HeatingPrice(
            heating_wholesale_price_fraction=self.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'],
            heat_transfer_loss=self.config_data['AreaInfo']["HeatTransferLoss"])
        self.electricity_pricing: ElectricityPrice = ElectricityPrice(
            elec_wholesale_offset=self.config_data['AreaInfo']['ExternalElectricityWholesalePriceOffset'],
            elec_tax=self.config_data['AreaInfo']["ElectricityTax"],
            elec_grid_fee=self.config_data['AreaInfo']["ElectricityGridFee"],
            elec_tax_internal=self.config_data['AreaInfo']["ElectricityTaxInternal"],
            elec_grid_fee_internal=self.config_data['AreaInfo']["ElectricityGridFeeInternal"],
            nordpool_data=external_price_data)

        self.buildings_mock_data: pd.DataFrame = get_generated_mock_data(self.config_id)
        self.trading_periods = pd.DatetimeIndex(get_intersection(self.buildings_mock_data.index.tolist(),
                                                self.electricity_pricing.get_external_price_data_datetimes()))\
            .sort_values()

        self.clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]] = {}
        self.storage_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}
        self.heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}

    def initialize_agents(self) -> Tuple[List[IAgent], List[GridAgent]]:
        # Register all agents
        # Keep a list of all agents to iterate over later
        agents: List[IAgent] = []
        grid_agents: List[GridAgent] = []

        # Read CSV files
        tornet_household_elec_cons, coop_elec_cons, tornet_heat_cons, coop_heat_cons = read_energy_data()
        irradiation_data = read_irradiation_data().set_index('datetime').squeeze()

        for agent in self.config_data["Agents"]:
            agent_type = agent["Type"]
            agent_name = agent['Name']

            if agent_type in ["BuildingAgent", "PVAgent", "GroceryStoreAgent"]:
                pv_prod_series = calculate_solar_prod(irradiation_data,
                                                      agent['PVArea'],
                                                      agent['PVEfficiency'])
            if agent_type == "BuildingAgent":
                agent_id = self.agent_specs[agent['Name']]
                elec_cons_series = self.buildings_mock_data[get_elec_cons_key(agent_id)]
                space_heat_cons_series = self.buildings_mock_data[get_space_heat_cons_key(agent_id)]
                hot_tap_water_cons_series = self.buildings_mock_data[get_hot_tap_water_cons_key(agent_id)]

                # We're not currently supporting different temperatures of heating,
                # it's just "heating" as a very simplifiedS
                # entity. Therefore we'll bunch them together here for now.
                total_heat_cons_series = space_heat_cons_series + hot_tap_water_cons_series

                building_digital_twin = StaticDigitalTwin(electricity_usage=elec_cons_series,
                                                          electricity_production=pv_prod_series,
                                                          heating_usage=total_heat_cons_series)

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
                grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=coop_elec_cons,
                                                               heating_usage=coop_heat_cons,
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

        # Load generated mock data
        logger.info("Generating data...")

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

            all_bids_dict_batch: Dict[datetime.datetime, Collection[NetBidWithAcceptanceStatus]] \
                = dict(zip(trading_periods_in_this_batch, ([] for _ in trading_periods_in_this_batch)))
            all_trades_dict_batch: Dict[datetime.datetime, Collection[Trade]] \
                = dict(zip(trading_periods_in_this_batch, ([] for _ in trading_periods_in_this_batch)))
            all_extra_costs_batch: List[ExtraCost] = []
            electricity_price_objs: List[TableElectricityPrice] = []

            # Loop over periods i batch
            for period in trading_periods_in_this_batch:
                if period.day == period.hour == 1:
                    info_string = "Simulations entering {:%B}".format(period)
                    logger.info(info_string)

                # Get all bids
                bids = [agent.make_bids(period, self.clearing_prices_historical) for agent in self.agents]

                # Flatten bids list
                bids_flat: List[GrossBid] = flatten_collection(bids)

                # Add in tax and grid fee for SELL bids (for electricity, heating is not taxed)
                net_bids = net_bids_from_gross_bids(bids_flat, self.electricity_pricing)

                # Resolve bids
                clearing_prices, bids_with_acceptance_status = market_solver.resolve_bids(period, net_bids)
                self.clearing_prices_historical[period] = clearing_prices

                all_bids_dict_batch[period] = bids_with_acceptance_status

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
                all_trades_dict_batch[period] = all_trades_for_period

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

                electricity_price_objs.append(TableElectricityPrice(
                    job_id=self.job_id, period=period, retail_price=retail_price_elec,
                    wholesale_price=wholesale_price_elec))

                all_extra_costs_batch.extend(extra_costs)

            logger.info('Saving to db...')
            bid_objs = bids_to_db_objects(all_bids_dict_batch, self.job_id)
            trade_objs = trades_to_db_objects(all_trades_dict_batch, self.job_id)
            extra_cost_objs = extra_costs_to_db_objects(all_extra_costs_batch, self.job_id)
            bulk_insert(bid_objs + trade_objs + extra_cost_objs + electricity_price_objs)
        
        clearing_prices_objs = clearing_prices_to_db_objects(self.clearing_prices_historical, self.job_id)
        heat_pump_level_objs = levels_to_db_objects(self.heat_pump_levels_dict,
                                                    TradeMetadataKey.HEAT_PUMP_WORKLOAD.name, self.job_id)
        storage_level_objs = levels_to_db_objects(self.storage_levels_dict,
                                                  TradeMetadataKey.STORAGE_LEVEL.name, self.job_id)
        bulk_insert(clearing_prices_objs + heat_pump_level_objs + storage_level_objs)

        logger.info("Finished simulating trades, beginning calculations on district heating price...")

    def extract_results(self):
        """
        Simulations finished. Now, we need to go through and calculate the exact district heating price for each month
        """
        logger.info('Calculating external_heating_prices')
        heating_price_lst = get_external_heating_prices(self.heat_pricing, self.trading_periods)
        heating_price_objs = external_heating_prices_to_db_objects(heating_price_lst, self.job_id)
        bulk_insert(heating_price_objs)

        logger.info('Calculating heat_cost_discr_corrections')
        heating_prices = pd.DataFrame.from_records(heating_price_lst)
        heat_cost_discr_corrections = correct_for_exact_heating_price(self.trading_periods,
                                                                      heating_prices,
                                                                      self.job_id)
        logger.info('Saving extra costs to db...')
        objs = extra_costs_to_db_objects(heat_cost_discr_corrections, self.job_id)
        bulk_insert(objs)
        # we inserted this into the database, and it's big (2GB), so delete from RAM
        del heat_cost_discr_corrections, objs
        gc.collect()

        # logger.info("Formatting results...")

        # self.progress.increase(0.05)
        # self.progress.display()

        # logger.info('Aggregating results per agent')
        # exact_retail_heat_price_by_ym, exact_wholesale_heat_price_by_ym = db_to_heating_price_dicts(self.job_id)
        # results_by_agent = results_calculator.calc_basic_results(self.agents, self.job_id,
        #                                                          self.exact_retail_electricity_prices_by_period,
        #                                                          self.exact_wholesale_electricity_prices_by_period,
        #                                                          exact_retail_heat_price_by_ym,
        #                                                          exact_wholesale_heat_price_by_ym)
        # self.progress.increase(0.005)
        # self.progress.display()

        # logger.info('Read trades from db...')
        # all_trades_df = db_to_trade_df(self.job_id)
        # self.progress.increase(0.005)
        # self.progress.display()
        # logger.info('Read bids from db...')
        # all_bids_df = db_to_bid_df(self.job_id)
        # logger.info('Read extra costs from db...')
        # extra_costs_df = db_to_extra_cost_df(self.job_id).sort_values(['period', 'agent'])

        # self.progress.final()
        # self.progress.display()

        # tax_paid = get_total_tax_paid(self.job_id)
        # grid_fees_paid_on_internal_trades = get_total_grid_fee_paid_on_internal_trades(self.job_id)

        # sim_res = SimulationResults(clearing_prices_historical=self.clearing_prices_historical,
        #                             all_trades=all_trades_df,
        #                             all_extra_costs=extra_costs_df,
        #                             all_bids=all_bids_df,
        #                             storage_levels_dict=self.storage_levels_dict,
        #                             heat_pump_levels_dict=self.heat_pump_levels_dict,
        #                             config_data=self.config_data,
        #                             agents=self.agents,
        #                             pricing=[self.heat_pricing, self.electricity_pricing],
        #                             grid_fees_paid_on_internal_trades=grid_fees_paid_on_internal_trades,
        #                             tax_paid=tax_paid,
        #                             exact_retail_heating_prices_by_year_and_month=exact_retail_heat_price_by_ym,
        #                             exact_wholesale_heating_prices_by_year_and_month=exact_wholesale_heat_price_by_ym,
        #                             results_by_agent=results_by_agent
        #                             )
        
        logger.info('Simulation finished!')

        # return sim_res
