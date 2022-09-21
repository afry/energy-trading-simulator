import datetime
import logging
import math
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from tradingplatformpoc import trading_platform_utils
from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_buying, \
    get_price_and_market_to_use_when_selling
from tradingplatformpoc.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.heat_pump import HeatPump
from tradingplatformpoc.trade import Trade, TradeMetadataKey
from tradingplatformpoc.trading_platform_utils import minus_n_hours

logger = logging.getLogger(__name__)


class BuildingAgent(IAgent):

    digital_twin: StaticDigitalTwin
    n_heat_pumps: int
    workloads_data: OrderedDict[int, Tuple[float, float]]  # Keys should be strictly increasing
    allow_sell_heat: bool

    def __init__(self, data_store: DataStore, digital_twin: StaticDigitalTwin, nbr_heat_pumps: int = 0,
                 coeff_of_perf: Optional[float] = None, guid="BuildingAgent"):
        super().__init__(guid, data_store)
        self.digital_twin = digital_twin
        self.n_heat_pumps = nbr_heat_pumps
        self.workloads_data = construct_workloads_data(coeff_of_perf, nbr_heat_pumps)
        self.allow_sell_heat = False

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None) -> List[GrossBid]:
        # The building should make a bid for purchasing energy, or selling if it has a surplus
        prev_period = trading_platform_utils.minus_n_hours(period, 1)
        prev_prices = self.data_store.get_local_price_if_exists_else_external_estimate(prev_period,
                                                                                       clearing_prices_historical)
        return self.make_bids_with_heat_pump(period, prev_prices[Resource.ELECTRICITY],
                                             prev_prices[Resource.HEATING])

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
                                         accepted_bids_for_agent: List[NetBidWithAcceptanceStatus]) -> \
            Tuple[List[Trade], Dict[TradeMetadataKey, Any]]:
        trades = []
        elec_retail_price = self.data_store.get_estimated_retail_price(period, Resource.ELECTRICITY, True)
        elec_wholesale_price = self.data_store.get_estimated_wholesale_price(period, Resource.ELECTRICITY)
        heat_retail_price = self.data_store.get_estimated_retail_price(period, Resource.HEATING, True)
        heat_wholesale_price = self.data_store.get_estimated_wholesale_price(period, Resource.HEATING)

        elec_net_consumption_pred = self.make_prognosis(period, Resource.ELECTRICITY)
        heat_net_consumption_pred = self.make_prognosis(period, Resource.HEATING)
        elec_clearing_price = clearing_prices[Resource.ELECTRICITY]
        heat_clearing_price = clearing_prices[Resource.HEATING]
        # Re-calculate optimal workload, now that prices are known
        workload_to_use = self.calculate_optimal_workload(elec_net_consumption_pred, heat_net_consumption_pred,
                                                          elec_clearing_price, heat_clearing_price)
        elec_needed_for_1_heat_pump = self.workloads_data[workload_to_use][0]
        heat_output_for_1_heat_pump = self.workloads_data[workload_to_use][1]

        # Now, the trading period "happens", some resources are consumed, some produced...
        elec_usage = self.get_actual_usage(period, Resource.ELECTRICITY)
        heat_usage = self.get_actual_usage(period, Resource.HEATING)
        elec_net_consumption_incl_pump = elec_usage + elec_needed_for_1_heat_pump * self.n_heat_pumps
        heat_net_consumption_incl_pump = heat_usage - heat_output_for_1_heat_pump * self.n_heat_pumps
        if elec_net_consumption_incl_pump > 0:
            # Positive net consumption, so need to buy electricity
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(elec_clearing_price,
                                                                                  elec_retail_price)
            trades.append(self.construct_elec_trade(Action.BUY, elec_net_consumption_incl_pump,
                                                    price_to_use, market_to_use, period))
        elif elec_net_consumption_incl_pump < 0:
            # Negative net consumption, meaning there is a surplus, which the agent will sell
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(elec_clearing_price,
                                                                                   elec_wholesale_price)
            # NOTE: Here we assume that even if we sell electricity on the "external market", we still pay
            # the internal electricity tax, and the internal grid fee
            trades.append(self.construct_elec_trade(Action.SELL, -elec_net_consumption_incl_pump,
                                                    price_to_use, market_to_use, period,
                                                    tax_paid=self.data_store.elec_tax_internal,
                                                    grid_fee_paid=self.data_store.elec_grid_fee_internal))
        if heat_net_consumption_incl_pump > 0:
            # Positive net consumption, so need to buy heating
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(heat_clearing_price,
                                                                                  heat_retail_price)
            trades.append(self.construct_buy_heat_trade(heat_net_consumption_incl_pump,
                                                        price_to_use, market_to_use, period))
        elif heat_net_consumption_incl_pump < 0:
            # Negative net consumption, meaning there is a surplus, which the agent will sell
            if self.allow_sell_heat:
                price_to_use, market_to_use = get_price_and_market_to_use_when_selling(heat_clearing_price,
                                                                                       heat_wholesale_price)
                trades.append(self.construct_sell_heat_trade(-heat_net_consumption_incl_pump,
                                                             price_to_use, market_to_use, period))
            else:
                logger.debug('For period {}, had excess heat of {:.2f} kWh, but could not sell that surplus. This heat '
                             'will be seen as having effectively vanished'.
                             format(period, -heat_net_consumption_incl_pump))
                # Notes here: Perhaps this surplus could be exported to an accumulator tank.
                # If not, then in reality what would presumably happen is that the buildings would be heated up more
                # than necessary, which would presumably lower the heat demand in subsequent periods. This is left as
                # a possible future improvement.
        return trades, {TradeMetadataKey.HEAT_PUMP_WORKLOAD: workload_to_use}

    def make_bids_with_heat_pump(self, period: datetime.datetime, pred_elec_price: float, pred_heat_price: float) -> \
            List[GrossBid]:
        """
        Note that if the agent doesn't have any heat pumps, this method will still work.
        """

        heat_net_consumption = self.make_prognosis(period, Resource.HEATING)
        elec_net_consumption = self.make_prognosis(period, Resource.ELECTRICITY)  # Negative means net production
        workload_to_use = self.calculate_optimal_workload(elec_net_consumption, heat_net_consumption, pred_elec_price,
                                                          pred_heat_price)
        elec_needed_for_1_heat_pump = self.workloads_data[workload_to_use][0]
        heat_output_for_1_heat_pump = self.workloads_data[workload_to_use][1]

        # Now we have decided what workload to use. Next, construct bids
        bids = []
        elec_net_consumption_incl_pump = elec_net_consumption + elec_needed_for_1_heat_pump * self.n_heat_pumps
        heat_net_consumption_incl_pump = heat_net_consumption - heat_output_for_1_heat_pump * self.n_heat_pumps
        if elec_net_consumption_incl_pump > 0:
            bids.append(self.construct_elec_bid(Action.BUY, elec_net_consumption_incl_pump, math.inf))
            # This demand must be fulfilled - therefore price is inf
        elif elec_net_consumption_incl_pump < 0:
            # What price to use here? The predicted local clearing price, or the external grid wholesale price?
            # Going with the latter
            bids.append(self.construct_elec_bid(Action.SELL, -elec_net_consumption_incl_pump,
                                                self.get_external_grid_buy_price(period, Resource.ELECTRICITY)))
        if heat_net_consumption_incl_pump > 0:
            bids.append(self.construct_buy_heat_bid(heat_net_consumption_incl_pump, math.inf))
            # This demand must be fulfilled - therefore price is inf
        elif heat_net_consumption_incl_pump < 0 and self.allow_sell_heat:
            # What price to use here? The predicted local clearing price, or the external grid wholesale price?
            # External grid may not want to buy heat at all, so going with the former, for now.
            bids.append(self.construct_sell_heat_bid(-heat_net_consumption_incl_pump, pred_heat_price))
        return bids

    def calculate_optimal_workload(self, elec_net_consumption: float, heat_net_consumption: float,
                                   pred_elec_price: float, pred_heat_price: float) -> int:
        """
        Calculates the optimal workload to run the agent's heat pumps. "Optimal" is the workload which leads to the
        lowest cost - the cost stemming from the import of electricity and/or heating, minus any income from electricity
        sold.
        """
        # Gross price, since we are interested in calculating our potential profit
        elec_sell_price = self.data_store.get_electricity_gross_internal_price(pred_elec_price)
        heat_sell_price = pred_heat_price if self.allow_sell_heat else 0

        min_cost = 1e10  # Big placeholder number
        prev_cost = 1e10  # Big placeholder number
        workload_to_use = 0
        for workload, (elec, heat) in self.workloads_data.items():

            elec_net_consumption_incl_pump = elec_net_consumption + elec * self.n_heat_pumps
            heat_net_consumption_incl_pump = heat_net_consumption - heat * self.n_heat_pumps
            heat_supply = abs(np.minimum(0, heat_net_consumption_incl_pump))
            elec_supply = abs(np.minimum(0, elec_net_consumption_incl_pump))
            incomes = elec_supply * elec_sell_price + heat_supply * heat_sell_price
            heat_demand = np.maximum(0, heat_net_consumption_incl_pump)
            elec_demand = np.maximum(0, elec_net_consumption_incl_pump)
            expenditures = elec_demand * pred_elec_price + heat_demand + pred_heat_price
            expected_cost = expenditures - incomes

            if expected_cost > prev_cost:
                # Since the COP(workload) function is concave, the function of cost given a workload is convex.
                # Therefore, we know that if the cost for this workload is higher than the cost for the previous (lower)
                # workload, there is no point to look at any higher workloads, and we'll break out of this loop.
                # Note that this assumes that self.workloads_data is ordered and increasing!
                break

            if expected_cost < min_cost:
                min_cost = expected_cost
                workload_to_use = workload
            logger.debug('For workload {}, elec net consumption was {:.2f}, heat net consumption was {:.2f}, E[inc] was'
                         ' {:.2f}, E[exp] was {:.2f}, E[cost] was {:.2f}, COP was {:.2f}'.
                         format(int(workload), elec_net_consumption_incl_pump, heat_net_consumption_incl_pump,
                                incomes, expenditures, expected_cost, (heat / elec) if elec > 0 else 0))
            prev_cost = expected_cost
            if heat_supply > 0 and not self.allow_sell_heat:
                break  # No point in evaluating higher workloads - can't sell excess heat anyway
        return workload_to_use


def construct_workloads_data(coeff_of_perf: Optional[float], n_heat_pumps: int) -> \
        OrderedDict[int, Tuple[float, float]]:
    """
    Will construct a pd.DataFrame with three columns: workload, input, and output.
    If there are no heat pumps (n_heat_pumps = 0), the returned data frame will have only one row, which corresponds
    to not running a heat pump at all.
    """
    if n_heat_pumps == 0:
        ordered_dict = OrderedDict()
        ordered_dict[0] = (0.0, 0.0)
        return ordered_dict
    if coeff_of_perf is None:
        return HeatPump.calculate_for_all_workloads()
    return HeatPump.calculate_for_all_workloads(coeff_of_perf=coeff_of_perf)
