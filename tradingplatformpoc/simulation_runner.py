import datetime
import logging
import pickle
from typing import Any, Collection, Dict, List, Optional, Tuple, Union

import pandas as pd

from pkg_resources import resource_filename

import streamlit as st

from tradingplatformpoc import balance_manager, data_store, generate_mock_data, market_solver
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.balance_manager import correct_for_exact_heating_price
from tradingplatformpoc.bid import Action, GrossBid, NetBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.digitaltwin.storage_digital_twin import StorageDigitalTwin
from tradingplatformpoc.extra_cost import ExtraCost
from tradingplatformpoc.mock_data_generation_functions import MockDataKey, get_all_building_agents, get_elec_cons_key, \
    get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.results import results_calculator
from tradingplatformpoc.results.simulation_results import SimulationResults
from tradingplatformpoc.trade import Trade, TradeMetadataKey
from tradingplatformpoc.trading_platform_utils import calculate_solar_prod, flatten_collection, \
    get_if_exists_else, get_intersection

FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED = 0.065

logger = logging.getLogger(__name__)


class TradingSimulator:
    def __init__(self, config_data: Dict[str, Any], mock_datas_pickle_path: str):
        self.config_data = config_data
        self.mock_datas_pickle_path = mock_datas_pickle_path

        # Initialize data store
        self.data_store_entity = DataStore.from_csv_files(config_area_info=self.config_data["AreaInfo"])

        # Specify path for CSV files from which to take some mock data (currently only for grocery store)
        self.energy_data_csv_path = resource_filename("tradingplatformpoc.data", "full_mock_energy_data.csv")

        self.buildings_mock_data: pd.DataFrame = get_generated_mock_data(self.config_data, self.mock_datas_pickle_path)

        self.trading_periods = get_intersection(self.buildings_mock_data.index.tolist(),
                                                self.data_store_entity.get_nordpool_data_datetimes())

        self.clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]] = {}
        self.all_trades_dict: Dict[datetime.datetime, Collection[Trade]] \
            = dict(zip(self.trading_periods, ([] for _ in self.trading_periods)))
        self.all_bids_dict: Dict[datetime.datetime, Collection[NetBidWithAcceptanceStatus]] \
            = dict(zip(self.trading_periods, ([] for _ in self.trading_periods)))
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

        # Read energy CSV file
        tornet_household_elec_cons, coop_elec_cons, tornet_heat_cons, coop_heat_cons = \
            data_store.read_energy_data(self.energy_data_csv_path)

        for agent in self.config_data["Agents"]:
            agent_type = agent["Type"]
            agent_name = agent['Name']
            if agent_type == "BuildingAgent":
                elec_cons_series = self.buildings_mock_data[get_elec_cons_key(agent_name)]
                space_heat_cons_series = self.buildings_mock_data[get_space_heat_cons_key(agent_name)]
                hot_tap_water_cons_series = self.buildings_mock_data[get_hot_tap_water_cons_key(agent_name)]
                pv_efficiency = get_if_exists_else(agent, 'PVEfficiency', self.data_store_entity.default_pv_efficiency)
                pv_area = get_if_exists_else(agent, 'PVArea', self.data_store_entity.default_pv_area)
                pv_prod_series = calculate_solar_prod(self.data_store_entity.irradiation_data, pv_area, pv_efficiency)
                # We're not currently supporting different temperatures of heating,
                # it's just "heating" as a very simplified
                # entity. Therefore we'll bunch them together here for now.
                total_heat_cons_series = space_heat_cons_series + hot_tap_water_cons_series

                building_digital_twin = StaticDigitalTwin(electricity_usage=elec_cons_series,
                                                          electricity_production=pv_prod_series,
                                                          heating_usage=total_heat_cons_series)

                nbr_heat_pumps = agent["NumberHeatPumps"] if "NumberHeatPumps" in agent.keys() else 0
                cop = agent["COP"] if "COP" in agent.keys() else None

                agents.append(BuildingAgent(data_store=self.data_store_entity, digital_twin=building_digital_twin,
                                            guid=agent_name, nbr_heat_pumps=nbr_heat_pumps, coeff_of_perf=cop))

            elif agent_type == "StorageAgent":
                discharge_rate = agent["DischargeRate"] if "DischargeRate" in agent else agent["ChargeRate"]
                storage_digital_twin = StorageDigitalTwin(max_capacity_kwh=agent["Capacity"],
                                                          max_charge_rate_fraction=agent["ChargeRate"],
                                                          max_discharge_rate_fraction=discharge_rate,
                                                          discharging_efficiency=agent["RoundTripEfficiency"])
                agents.append(StorageAgent(self.data_store_entity, storage_digital_twin,
                                           resource=Resource[agent["Resource"]],
                                           n_hours_to_look_back=agent["NHoursBack"],
                                           buy_price_percentile=agent["BuyPricePercentile"],
                                           sell_price_percentile=agent["SellPricePercentile"],
                                           guid=agent_name))
            elif agent_type == "PVAgent":
                pv_efficiency = get_if_exists_else(agent, 'PVEfficiency', self.data_store_entity.default_pv_efficiency)
                pv_prod_series = calculate_solar_prod(self.data_store_entity.irradiation_data,
                                                      agent['PVArea'], pv_efficiency)
                pv_digital_twin = StaticDigitalTwin(electricity_production=pv_prod_series)
                agents.append(PVAgent(self.data_store_entity, pv_digital_twin, guid=agent_name))
            elif agent_type == "GroceryStoreAgent":
                pv_efficiency = get_if_exists_else(agent, 'PVEfficiency', self.data_store_entity.default_pv_efficiency)
                pv_area = agent['PVArea'] if 'PVArea' in agent else 0
                pv_prod_series = calculate_solar_prod(self.data_store_entity.irradiation_data, pv_area, pv_efficiency)
                grocery_store_digital_twin = StaticDigitalTwin(electricity_usage=coop_elec_cons,
                                                               heating_usage=coop_heat_cons,
                                                               electricity_production=pv_prod_series)
                agents.append(BuildingAgent(data_store=self.data_store_entity,
                                            digital_twin=grocery_store_digital_twin,
                                            guid=agent_name))
            elif agent_type == "GridAgent":
                grid_agent = GridAgent(self.data_store_entity, Resource[agent["Resource"]],
                                       max_transfer_per_hour=agent["TransferRate"], guid=agent_name)
                agents.append(grid_agent)
                grid_agents.append(grid_agent)

        # Verify that we have a Grid Agent
        if not any(isinstance(agent, GridAgent) for agent in agents):
            raise RuntimeError("No grid agent initialized")

        return agents, grid_agents

    def run(self, progress_bar: Union[st.progress, None] = None,
            progress_text: Union[st.info, None] = None) -> \
            SimulationResults:
        """
        The core loop of the simulation, running through the desired time period and performing trades.
        @param progress_bar             A streamlit progress bar, used only when running simulations through the UI
        @param progress_text            A streamlit info field, used only when running simulations through the UI
        """

        # Initialize metadata dictionaries
        placeholder_dict: Dict[datetime.datetime, Optional[float]] = \
            dict(zip(self.trading_periods, (None for _ in self.trading_periods)))
        self.storage_levels_dict: Dict[str, Dict[datetime.datetime, Optional[float]]] = \
            {agent.guid: placeholder_dict for agent in self.agents if isinstance(agent, StorageAgent)}
        
        self.heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, Optional[float]]] = \
            {agent.guid: placeholder_dict for agent in self.agents if hasattr(agent, "n_heat_pumps")}

        progress = Progress(progress_bar)
        logger.info("Starting trading simulations")

        # Load generated mock data
        if progress_text is not None:
            progress_text.info("Generating data...")

        # Main loop
        for period in self.trading_periods:
            if period.day == period.hour == 1:
                info_string = "Simulations entering {:%B}".format(period)
                logger.info(info_string)
                progress.increase(FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED)
                progress.display()
                if progress_text is not None:
                    progress_text.info(info_string + "...")

            # Get all bids
            bids = [agent.make_bids(period, self.clearing_prices_historical) for agent in self.agents]

            # Flatten bids list
            bids_flat: List[GrossBid] = flatten_collection(bids)

            # Add in tax and grid fee for SELL bids (for electricity, heating is not taxed)
            net_bids = net_bids_from_gross_bids(bids_flat, self.data_store_entity)

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
            grid_fees_paid_on_internal_trades = self.grid_fees_paid_on_internal_trades + grid_fees_paid_period
            # Sum up tax paid
            tax_paid_period = sum([trade.get_total_tax_paid() for trade in all_trades_for_period])
            tax_paid = self.tax_paid + tax_paid_period

            external_heating_sell_quantity = get_quantity_heating_sold_by_external_grid(external_trades)
            self.data_store_entity.add_external_heating_sell(period, external_heating_sell_quantity)

            wholesale_price_elec = self.data_store_entity.get_exact_wholesale_price(period, Resource.ELECTRICITY)
            retail_price_elec = self.data_store_entity.get_exact_retail_price(period, Resource.ELECTRICITY,
                                                                              include_tax=True)
            wholesale_prices = {Resource.ELECTRICITY: wholesale_price_elec,
                                Resource.HEATING: self.data_store_entity
                                .get_estimated_wholesale_price(period, Resource.HEATING)}
            extra_costs = balance_manager.calculate_penalty_costs_for_period(bids_with_acceptance_status,
                                                                             all_trades_for_period,
                                                                             period,
                                                                             clearing_prices,
                                                                             wholesale_prices)
            self.exact_wholesale_electricity_prices_by_period[period] = wholesale_price_elec
            self.exact_retail_electricity_prices_by_period[period] = retail_price_elec
            self.all_extra_costs.extend(extra_costs)

        progress.increase(FRACTION_OF_CALC_TIME_FOR_1_MONTH_SIMULATED + 0.01)  # Final month
        progress.display()
        if progress_text is not None:
            progress_text.info("Simulated a full year, starting some calculations on district heating price...")

        # Simulations finished. Now, we need to go through and calculate the exact district heating price for each month
        logger.info('Calculating external_heating_prices')
        estimated_retail_heat_price_by_ym, \
            estimated_wholesale_heat_price_by_ym, \
            exact_retail_heat_price_by_ym, \
            exact_wholesale_heat_price_by_ym = get_external_heating_prices(self.data_store_entity, self.trading_periods)

        logger.info('Calculating heat_cost_discr_corrections')
        heat_cost_discr_corrections = correct_for_exact_heating_price(self.trading_periods, self.all_trades_dict,
                                                                      exact_retail_heat_price_by_ym,
                                                                      exact_wholesale_heat_price_by_ym,
                                                                      estimated_retail_heat_price_by_ym,
                                                                      estimated_wholesale_heat_price_by_ym)
        self.all_extra_costs.extend(heat_cost_discr_corrections)

        if progress_text is not None:
            progress_text.info("Formatting results...")

        logger.info('Creating extra_costs_df')
        extra_costs_df = pd.DataFrame([x.to_series() for x in self.all_extra_costs]).sort_values(['period', 'agent'])
        progress.increase(0.05)
        progress.display()

        all_trades_df = construct_df_from_datetime_dict(self.all_trades_dict)
        progress.increase(0.005)
        progress.display()
        all_bids_df = construct_df_from_datetime_dict(self.all_bids_dict)
        progress.increase(0.005)
        progress.display()

        logger.info('Aggregating results per agent')
        if progress_text is not None:
            progress_text.info("Aggregating results per agent...")
        results_by_agent = results_calculator.calc_basic_results(self.agents, all_trades_df, extra_costs_df,
                                                                 self.exact_retail_electricity_prices_by_period,
                                                                 self.exact_wholesale_electricity_prices_by_period,
                                                                 exact_retail_heat_price_by_ym,
                                                                 exact_wholesale_heat_price_by_ym)
        progress.final()
        progress.display()

        sim_res = SimulationResults(clearing_prices_historical=self.clearing_prices_historical,
                                    all_trades=all_trades_df,
                                    all_extra_costs=extra_costs_df,
                                    all_bids=all_bids_df,
                                    storage_levels_dict=self.storage_levels_dict,
                                    heat_pump_levels_dict=self.heat_pump_levels_dict,
                                    config_data=self.config_data,
                                    agents=self.agents,
                                    data_store=self.data_store_entity,
                                    grid_fees_paid_on_internal_trades=grid_fees_paid_on_internal_trades,
                                    tax_paid=tax_paid,
                                    exact_retail_heating_prices_by_year_and_month=exact_retail_heat_price_by_ym,
                                    exact_wholesale_heating_prices_by_year_and_month=exact_wholesale_heat_price_by_ym,
                                    results_by_agent=results_by_agent
                                    )
        return sim_res


def net_bids_from_gross_bids(gross_bids: List[GrossBid], data_store_entity: DataStore) -> List[NetBid]:
    """
    Add in internal tax and internal grid fee for internal SELL bids (for electricity, heating is not taxed).
    Note: External electricity bids already have grid fee
    """
    net_bids: List[NetBid] = []
    for bid in gross_bids:
        if bid.action == Action.SELL and bid.resource == Resource.ELECTRICITY:
            if bid.by_external:
                net_price = data_store_entity.get_electricity_net_external_price(bid.price)
                net_bids.append(NetBid.from_gross_bid(bid, net_price))
            else:
                net_price = data_store_entity.get_electricity_net_internal_price(bid.price)
                net_bids.append(NetBid.from_gross_bid(bid, net_price))
        else:
            net_bids.append(NetBid.from_gross_bid(bid, bid.price))
    return net_bids


class Progress:
    def __init__(self, progress_bar: Union[st.progress, None] = None):
        self.frac_complete = 0.0
        self.progress_bar = progress_bar

    def get_process(self):
        return self.frac_complete

    def increase(self, increase_by: float):
        """
        Increases the progress bar, and returns its current value.
        """
        # Capping at 0.0 and 1.0 to avoid StreamlitAPIException
        self.frac_complete = min(1.0, max(0.0, self.frac_complete + increase_by))

    def final(self):
        self.frac_complete = 1.0

    def display(self):
        frac_complete = self.get_process()
        if self.progress_bar is not None:
            self.progress_bar.progress(frac_complete)


def go_through_trades_metadata(metadata: Dict[TradeMetadataKey, Any], period: datetime.datetime, agent_guid: str,
                               heat_pump_levels_dict: Dict[str, Dict[datetime.datetime, Optional[float]]],
                               storage_levels_dict: Dict[str, Dict[datetime.datetime, Optional[float]]]):
    """
    The agent may want to send some metadata along with its trade, to the simulation runner. Any such metadata is dealt
    with here.
    """
    for metadata_key in metadata:
        if metadata_key == TradeMetadataKey.STORAGE_LEVEL:
            storage_levels_dict[agent_guid][period] = metadata[metadata_key]  # capacity_for_agent
        elif metadata_key == TradeMetadataKey.HEAT_PUMP_WORKLOAD:
            heat_pump_levels_dict[agent_guid][period] = metadata[metadata_key]  # current_heat_pump_level
        else:
            logger.info('Encountered unexpected metadata! Key: {}, Value: {}'.
                        format(metadata_key, metadata[metadata_key]))


def get_external_heating_prices(data_store_entity: DataStore, trading_periods: Collection[datetime.datetime]) -> \
        Tuple[Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float],
              Dict[Tuple[int, int], float]]:
    exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    estimated_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    estimated_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float] = {}
    for (year, month) in set([(dt.year, dt.month) for dt in trading_periods]):
        first_day_of_month = datetime.datetime(year, month, 1)  # Which day it is doesn't matter
        exact_retail_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_exact_retail_price(first_day_of_month, Resource.HEATING, include_tax=True)
        exact_wholesale_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_exact_wholesale_price(first_day_of_month, Resource.HEATING)
        estimated_retail_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_estimated_retail_price(first_day_of_month, Resource.HEATING, include_tax=True)
        estimated_wholesale_heating_prices_by_year_and_month[(year, month)] = \
            data_store_entity.get_estimated_wholesale_price(first_day_of_month, Resource.HEATING)
    return estimated_retail_heating_prices_by_year_and_month, \
        estimated_wholesale_heating_prices_by_year_and_month, \
        exact_retail_heating_prices_by_year_and_month, \
        exact_wholesale_heating_prices_by_year_and_month


def get_generated_mock_data(config_data: dict, mock_datas_pickle_path: str) -> pd.DataFrame:
    """
    Loads the dict stored in MOCK_DATAS_PICKLE, checks if it contains a key which is identical to the set of building
    agents specified in config_data. If it isn't, throws an error. If it is, it returns the value for that key in the
    dictionary.
    @param config_data: A dictionary specifying agents etc
    @param mock_datas_pickle_path: Path to pickle file where dict with mock data is saved
    @return: A pd.DataFrame containing mock data for building agents
    """
    with open(mock_datas_pickle_path, 'rb') as f:
        all_data_sets = pickle.load(f)
    building_agents, total_gross_floor_area = get_all_building_agents(config_data["Agents"])
    mock_data_key = MockDataKey(frozenset(building_agents), frozenset(config_data["MockDataConstants"].items()))
    if mock_data_key not in all_data_sets:
        logger.info("No mock data found for this configuration. Running mock data generation.")
        all_data_sets = generate_mock_data.run(config_data)
        logger.info("Finished mock data generation.")
    return all_data_sets[mock_data_key].to_pandas().set_index('datetime')


def get_quantity_heating_sold_by_external_grid(external_trades: List[Trade]) -> float:
    return sum([x.quantity_post_loss for x in external_trades if
                (x.resource == Resource.HEATING) & (x.action == Action.SELL)])


def construct_df_from_datetime_dict(some_dict: Union[Dict[datetime.datetime, Collection[NetBidWithAcceptanceStatus]],
                                                     Dict[datetime.datetime, Collection[Trade]]]) \
        -> pd.DataFrame:
    """
    Streamlit likes to deal with pd.DataFrames, so we'll save data in that format.
    """
    logger.info('Constructing dataframe from datetime dict')
    return pd.DataFrame([x.to_dict_with_period(period) for period, some_collection in some_dict.items()
                         for x in some_collection])
