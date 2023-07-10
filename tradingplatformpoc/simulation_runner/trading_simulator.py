import datetime
import logging
from typing import Any, Collection, Dict, List, Tuple, Union

import pandas as pd

import streamlit as st

from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.data.data_series_from_file import read_energy_data, read_irradiation_data, read_nordpool_data
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.generate_data.mock_data_generation_functions import get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.market import balance_manager
from tradingplatformpoc.market import market_solver
from tradingplatformpoc.market.balance_manager import correct_for_exact_heating_price
from tradingplatformpoc.market.bid import GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.extra_cost import ExtraCost
from tradingplatformpoc.market.trade import Trade
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.results import results_calculator
from tradingplatformpoc.results.simulation_results import SimulationResults
from tradingplatformpoc.simulation_runner.progress import Progress
from tradingplatformpoc.simulation_runner.simulation_utils import construct_df_from_datetime_dict,  \
    get_external_heating_prices, get_generated_mock_data, get_quantity_heating_sold_by_external_grid, \
    go_through_trades_metadata, net_bids_from_gross_bids
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod, flatten_collection, \
    get_intersection

FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED = 0.065

logger = logging.getLogger(__name__)


class TradingSimulator:
    def __init__(self, config_data: Dict[str, Any], mock_datas_pickle_path: str):
        self.config_data = config_data
        self.mock_datas_pickle_path = mock_datas_pickle_path

        # Read data form files
        # TODO: To be changed
        self.external_price_data = read_nordpool_data()

        self.heat_pricing: HeatingPrice = HeatingPrice(self.config_data['AreaInfo'])
        self.electricity_pricing: ElectricityPrice = ElectricityPrice(self.config_data['AreaInfo'],
                                                                      self.external_price_data)

        self.buildings_mock_data: pd.DataFrame = get_generated_mock_data(self.config_data, self.mock_datas_pickle_path)

        self.trading_periods = get_intersection(self.buildings_mock_data.index.tolist(),
                                                self.electricity_pricing.get_external_price_data_datetimes())

        self.clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]] = {}
        self.all_trades_dict: Dict[datetime.datetime, Collection[Trade]] \
            = dict(zip(self.trading_periods, ([] for _ in self.trading_periods)))
        self.all_bids_dict: Dict[datetime.datetime, Collection[NetBidWithAcceptanceStatus]] \
            = dict(zip(self.trading_periods, ([] for _ in self.trading_periods)))
        self.storage_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}
        self.heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, float]] = {}
        self.all_extra_costs: List[ExtraCost] = []
        # Store the exact external prices, need them for some calculations
        self.exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float] \
            = dict(zip(self.trading_periods, (0.0 for _ in self.trading_periods)))
        self.exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float] \
            = dict(zip(self.trading_periods, (0.0 for _ in self.trading_periods)))
        # Amount of tax paid
        self.tax_paid = 0.0
        # Amount of grid fees paid on internal trades
        self.grid_fees_paid_on_internal_trades = 0.0
        self.agents, self.grid_agents = self.initialize_agents()

    def initialize_agents(self) -> Tuple[List[IAgent], List[GridAgent]]:
        # Register all agents
        # Keep a list of all agents to iterate over later
        agents: List[IAgent] = []
        grid_agents: List[GridAgent] = []

        # Read CSV files
        tornet_household_elec_cons, coop_elec_cons, tornet_heat_cons, coop_heat_cons = read_energy_data()
        irradiation_data = read_irradiation_data()

        for agent in self.config_data["Agents"]:
            agent_type = agent["Type"]
            agent_name = agent['Name']

            if agent_type in ["BuildingAgent", "PVAgent", "GroceryStoreAgent"]:
                pv_prod_series = calculate_solar_prod(irradiation_data,
                                                      agent['PVArea'],
                                                      agent['PVEfficiency'])
            if agent_type == "BuildingAgent":
                elec_cons_series = self.buildings_mock_data[get_elec_cons_key(agent_name)]
                space_heat_cons_series = self.buildings_mock_data[get_space_heat_cons_key(agent_name)]
                hot_tap_water_cons_series = self.buildings_mock_data[get_hot_tap_water_cons_key(agent_name)]

                # We're not currently supporting different temperatures of heating,
                # it's just "heating" as a very simplified
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

            elif agent_type == "StorageAgent":
                storage_digital_twin = StorageDigitalTwin(max_capacity_kwh=agent["Capacity"],
                                                          max_charge_rate_fraction=agent["ChargeRate"],
                                                          max_discharge_rate_fraction=agent["DischargeRate"],
                                                          discharging_efficiency=agent["RoundTripEfficiency"])
                agents.append(StorageAgent(self.electricity_pricing, storage_digital_twin,
                                           resource=Resource[agent["Resource"]],
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

    def run(self, progress_bar: Union[st.progress, None] = None,
            progress_text: Union[st.info, None] = None) -> SimulationResults:
        """
        The core loop of the simulation, running through the desired time period and performing trades.
        @param progress_bar             A streamlit progress bar, used only when running simulations through the UI
        @param progress_text            A streamlit info field, used only when running simulations through the UI
        """

        self.progress = Progress(progress_bar)
        self.progress_text = progress_text
        logger.info("Starting trading simulations")

        # Load generated mock data
        if self.progress_text is not None:
            self.progress_text.info("Generating data...")

        # Main loop
        for period in self.trading_periods:
            if period.day == period.hour == 1:
                info_string = "Simulations entering {:%B}".format(period)
                logger.info(info_string)
                self.progress.increase(FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED)
                self.progress.display()
                if self.progress_text is not None:
                    self.progress_text.info(info_string + "...")

            # Get all bids
            bids = [agent.make_bids(period, self.clearing_prices_historical) for agent in self.agents]

            # Flatten bids list
            bids_flat: List[GrossBid] = flatten_collection(bids)

            # Add in tax and grid fee for SELL bids (for electricity, heating is not taxed)
            net_bids = net_bids_from_gross_bids(bids_flat, self.electricity_pricing)

            # Resolve bids
            clearing_prices, bids_with_acceptance_status = market_solver.resolve_bids(period, net_bids)
            self.clearing_prices_historical[period] = clearing_prices

            self.all_bids_dict[period] = bids_with_acceptance_status

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
            external_trades = flatten_collection([ga.calculate_external_trades(trades_excl_external, clearing_prices)
                                                 for ga in self.grid_agents])
            all_trades_for_period = trades_excl_external + external_trades
            self.all_trades_dict[period] = all_trades_for_period

            # Sum up grid fees paid
            grid_fees_paid_period = sum([trade.get_total_grid_fee_paid() for trade in trades_excl_external])
            self.grid_fees_paid_on_internal_trades = self.grid_fees_paid_on_internal_trades + grid_fees_paid_period
            # Sum up tax paid
            tax_paid_period = sum([trade.get_total_tax_paid() for trade in all_trades_for_period])
            self.tax_paid = self.tax_paid + tax_paid_period

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
            self.exact_wholesale_electricity_prices_by_period[period] = wholesale_price_elec
            self.exact_retail_electricity_prices_by_period[period] = retail_price_elec
            self.all_extra_costs.extend(extra_costs)

        self.progress.increase(FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED + 0.01)  # Final month
        self.progress.display()
        if self.progress_text is not None:
            self.progress_text.info("Simulated a full year, starting some calculations on district heating price...")

        return self.extract_results()

    def extract_results(self) -> SimulationResults:
        """
        Simulations finished. Now, we need to go through and calculate the exact district heating price for each month
        """
        logger.info('Calculating external_heating_prices')
        estimated_retail_heat_price_by_ym, \
            estimated_wholesale_heat_price_by_ym, \
            exact_retail_heat_price_by_ym, \
            exact_wholesale_heat_price_by_ym = get_external_heating_prices(self.heat_pricing,
                                                                           self.trading_periods)

        logger.info('Calculating heat_cost_discr_corrections')
        heat_cost_discr_corrections = correct_for_exact_heating_price(self.trading_periods, self.all_trades_dict,
                                                                      exact_retail_heat_price_by_ym,
                                                                      exact_wholesale_heat_price_by_ym,
                                                                      estimated_retail_heat_price_by_ym,
                                                                      estimated_wholesale_heat_price_by_ym)
        self.all_extra_costs.extend(heat_cost_discr_corrections)

        if self.progress_text is not None:
            self.progress_text.info("Formatting results...")

        logger.info('Creating extra_costs_df')
        # this takes 2 minutes
        extra_costs_df = pd.DataFrame.from_records(({'period': x.period,
                                                     'agent': x.agent,
                                                     'cost_type': x.cost_type,
                                                     'cost': x.cost}
                                                    for x in self.all_extra_costs)).sort_values(['period', 'agent'])
        self.progress.increase(0.05)
        self.progress.display()

        all_trades_df = construct_df_from_datetime_dict(self.all_trades_dict)
        self.progress.increase(0.005)
        self.progress.display()
        all_bids_df = construct_df_from_datetime_dict(self.all_bids_dict)
        self.progress.increase(0.005)
        self.progress.display()

        logger.info('Aggregating results per agent')
        if self.progress_text is not None:
            self.progress_text.info("Aggregating results per agent...")
        results_by_agent = results_calculator.calc_basic_results(self.agents, all_trades_df, extra_costs_df,
                                                                 self.exact_retail_electricity_prices_by_period,
                                                                 self.exact_wholesale_electricity_prices_by_period,
                                                                 exact_retail_heat_price_by_ym,
                                                                 exact_wholesale_heat_price_by_ym)
        self.progress.final()
        self.progress.display()

        sim_res = SimulationResults(clearing_prices_historical=self.clearing_prices_historical,
                                    all_trades=all_trades_df,
                                    all_extra_costs=extra_costs_df,
                                    all_bids=all_bids_df,
                                    storage_levels_dict=self.storage_levels_dict,
                                    heat_pump_levels_dict=self.heat_pump_levels_dict,
                                    config_data=self.config_data,
                                    agents=self.agents,
                                    # data_store=self.data_store_entity,
                                    grid_fees_paid_on_internal_trades=self.grid_fees_paid_on_internal_trades,
                                    tax_paid=self.tax_paid,
                                    exact_retail_heating_prices_by_year_and_month=exact_retail_heat_price_by_ym,
                                    exact_wholesale_heating_prices_by_year_and_month=exact_wholesale_heat_price_by_ym,
                                    results_by_agent=results_by_agent
                                    )
        return sim_res
