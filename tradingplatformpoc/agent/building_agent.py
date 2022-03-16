import datetime
import logging
import math
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

from tradingplatformpoc import trading_platform_utils
from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_buying, \
    get_price_and_market_to_use_when_selling
from tradingplatformpoc.bid import Action, Bid, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.heat_pump import HeatPump
from tradingplatformpoc.trade import Trade
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES, minus_n_hours

logger = logging.getLogger(__name__)


class BuildingAgent(IAgent):

    def __init__(self, data_store: DataStore, digital_twin: StaticDigitalTwin, nbr_heat_pumps: int = 0,
                 coeff_of_perf: Optional[float] = None, guid="BuildingAgent"):
        super().__init__(guid, data_store)
        self.digital_twin = digital_twin
        self.n_heat_pumps = nbr_heat_pumps
        self.workloads_df = construct_workloads_df(coeff_of_perf, nbr_heat_pumps)
        self.allow_sell_heat = False

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None) -> List[Bid]:
        # The building should make a bid for purchasing energy, or selling if it has a surplus
        prev_period = trading_platform_utils.minus_n_hours(period, 1)
        prev_prices = self.data_store.get_local_price_if_exists_else_external_estimate(prev_period,
                                                                                       clearing_prices_historical)
        return self.make_bids_with_heat_pump(period, prev_prices[Resource.ELECTRICITY],
                                             prev_prices[Resource.HEATING], self.allow_sell_heat)

    def make_prognosis(self, period: datetime.datetime, resource: Resource) -> float:
        # The building should make a prognosis for how much energy will be required
        prev_trading_period = minus_n_hours(period, 1)
        try:
            electricity_demand_prev = self.digital_twin.get_consumption(prev_trading_period, resource)
            electricity_prod_prev = self.digital_twin.get_production(prev_trading_period, resource)
        except KeyError:
            # First time step, haven't got a previous value to use. Will go with a perfect prediction here
            electricity_demand_prev = self.digital_twin.get_consumption(period, resource)
            electricity_prod_prev = self.digital_twin.get_production(period, resource)
        return electricity_demand_prev - electricity_prod_prev

    def get_actual_usage(self, period: datetime.datetime, resource: Resource) -> float:
        actual_consumption = self.digital_twin.get_consumption(period, resource)
        actual_production = self.digital_twin.get_production(period, resource)
        return actual_consumption - actual_production

    def make_trades_given_clearing_price(self, period: datetime.datetime, clearing_prices: Dict[Resource, float],
                                         accepted_bids_for_agent: List[BidWithAcceptanceStatus]) -> List[Trade]:
        trades = []
        accepted_heat_sell_bid = [x for x in accepted_bids_for_agent if x.resource == Resource.HEATING
                                  and x.action == Action.SELL]
        had_sell_heat_bid_accepted = len(accepted_heat_sell_bid) > 0

        elec_usage = self.get_actual_usage(period, Resource.ELECTRICITY)
        heat_usage = self.get_actual_usage(period, Resource.HEATING)
        elec_clearing_price = clearing_prices[Resource.ELECTRICITY]
        heat_clearing_price = clearing_prices[Resource.HEATING]
        elec_retail_price = self.data_store.get_estimated_retail_price(period, Resource.ELECTRICITY)
        elec_wholesale_price = self.data_store.get_estimated_wholesale_price(period, Resource.ELECTRICITY)
        heat_retail_price = self.data_store.get_estimated_retail_price(period, Resource.HEATING)
        heat_wholesale_price = self.data_store.get_estimated_wholesale_price(period, Resource.HEATING)

        workload_to_use = self.calculate_optimal_workload(elec_usage, heat_usage, elec_clearing_price,
                                                          heat_clearing_price, had_sell_heat_bid_accepted)
        row_to_use = self.workloads_df.loc[self.workloads_df['workload'] == workload_to_use].iloc[0]
        elec_net_consumption_incl_pump = elec_usage + row_to_use['input'] * self.n_heat_pumps
        heat_net_consumption_incl_pump = heat_usage - row_to_use['output'] * self.n_heat_pumps

        if elec_net_consumption_incl_pump > 0:
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(elec_clearing_price,
                                                                                  elec_retail_price)
            trades.append(self.construct_trade(Action.BUY, Resource.ELECTRICITY, elec_net_consumption_incl_pump,
                                               price_to_use, market_to_use, period))
        elif elec_net_consumption_incl_pump < 0:
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(elec_clearing_price,
                                                                                   elec_wholesale_price)
            trades.append(self.construct_trade(Action.SELL, Resource.ELECTRICITY, -elec_net_consumption_incl_pump,
                                               price_to_use, market_to_use, period))
        if heat_net_consumption_incl_pump > 0:
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(heat_clearing_price,
                                                                                  heat_retail_price)
            trades.append(self.construct_trade(Action.BUY, Resource.HEATING, heat_net_consumption_incl_pump,
                                               price_to_use, market_to_use, period))
        elif heat_net_consumption_incl_pump < 0:
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(heat_clearing_price,
                                                                                   heat_wholesale_price)
            trades.append(self.construct_trade(Action.SELL, Resource.HEATING, -heat_net_consumption_incl_pump,
                                               price_to_use, market_to_use, period))
        return trades

    def make_bids_with_heat_pump(self, period: datetime.datetime, pred_elec_price: float, pred_heat_price: float,
                                 allow_selling_heat: bool) -> List[Bid]:
        """
        Note that if the agent doesn't have any heat pumps, this method will still work.
        """

        heat_net_consumption = self.make_prognosis(period, Resource.HEATING)
        elec_net_consumption = self.make_prognosis(period, Resource.ELECTRICITY)  # Negative means net production
        workload_to_use = self.calculate_optimal_workload(elec_net_consumption, heat_net_consumption, pred_elec_price,
                                                          pred_heat_price, allow_selling_heat)

        # Now we have decided what workload to use. Next, construct bids
        bids = []
        row_to_use = self.workloads_df.loc[self.workloads_df['workload'] == workload_to_use].iloc[0]
        elec_net_consumption_incl_pump = elec_net_consumption + row_to_use['input'] * self.n_heat_pumps
        heat_net_consumption_incl_pump = heat_net_consumption - row_to_use['output'] * self.n_heat_pumps
        if elec_net_consumption_incl_pump > 0:
            bids.append(self.construct_bid(Action.BUY, Resource.ELECTRICITY, elec_net_consumption_incl_pump, math.inf))
            # This demand must be fulfilled - therefore price is inf
        elif elec_net_consumption_incl_pump < 0:
            # What price to use here? The predicted local clearing price, or the external grid wholesale price?
            # Going with the latter
            bids.append(self.construct_bid(Action.SELL, Resource.ELECTRICITY, -elec_net_consumption_incl_pump,
                                           self.get_external_grid_buy_price(period, Resource.ELECTRICITY)))
        if heat_net_consumption_incl_pump > 0:
            bids.append(self.construct_bid(Action.BUY, Resource.HEATING, heat_net_consumption_incl_pump, math.inf))
            # This demand must be fulfilled - therefore price is inf
        elif heat_net_consumption_incl_pump < 0 and allow_selling_heat:
            # What price to use here? The predicted local clearing price, or the external grid wholesale price?
            # External grid may not want to buy heat at all, so going with the former, for now.
            bids.append(self.construct_bid(Action.SELL, Resource.HEATING, -heat_net_consumption_incl_pump,
                                           pred_heat_price))
        return bids

    def calculate_optimal_workload(self, elec_net_consumption: float, heat_net_consumption: float,
                                   pred_elec_price: float, pred_heat_price: float, allow_selling_heat: bool) -> int:
        elec_sell_price = pred_elec_price
        heat_sell_price = pred_heat_price if allow_selling_heat else 0

        min_cost = 1e10  # Big placeholder number
        workload_to_use = 0
        for index, row in self.workloads_df.iterrows():
            elec_net_consumption_incl_pump = elec_net_consumption + row['input'] * self.n_heat_pumps
            heat_net_consumption_incl_pump = heat_net_consumption - row['output'] * self.n_heat_pumps
            heat_supply = abs(np.minimum(0, heat_net_consumption_incl_pump))
            elec_supply = abs(np.minimum(0, elec_net_consumption_incl_pump))
            incomes = elec_supply * elec_sell_price + heat_supply * heat_sell_price
            heat_demand = np.maximum(0, heat_net_consumption_incl_pump)
            elec_demand = np.maximum(0, elec_net_consumption_incl_pump)
            expenditures = elec_demand * pred_elec_price + heat_demand + pred_heat_price
            expected_cost = expenditures - incomes
            if expected_cost < min_cost:
                min_cost = expected_cost
                workload_to_use = row['workload']
            logger.debug('For workload {}, elec net consumption was {:.2f}, heat net consumption was {:.2f}, E[inc] was'
                         ' {:.2f}, E[exp] was {:.2f}, E[cost] was {:.2f}, COP was {:.2f}'.
                         format(int(row['workload']), elec_net_consumption_incl_pump, heat_net_consumption_incl_pump,
                                incomes, expenditures, expected_cost,
                                (row['output'] / row['input']) if row['input'] > 0 else 0))
            if heat_supply > 0 and not allow_selling_heat:
                break  # No point in evaluating higher workloads - can't sell excess heat anyway
        return workload_to_use


def construct_workloads_df(coeff_of_perf: Optional[float], n_heat_pumps: int) -> pd.DataFrame:
    """
    Will construct a pd.DataFrame with three columns: workload, input, and output.
    If there are no heat pumps (n_heat_pumps = 0), the returned data frame will have only one row, which corresponds
    to not running a heat pump at all.
    """
    if n_heat_pumps == 0:
        return pd.DataFrame({'workload': [0], 'input': [0.0], 'output': [0.0]})
    if coeff_of_perf is None:
        return HeatPump.calculate_for_all_workloads()
    return HeatPump.calculate_for_all_workloads(coeff_of_perf=coeff_of_perf)
