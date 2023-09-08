import datetime
import logging
import math
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from tradingplatformpoc import trading_platform_utils
from tradingplatformpoc.agent.iagent import IAgent, get_price_and_market_to_use_when_buying, \
    get_price_and_market_to_use_when_selling
from tradingplatformpoc.digitaltwin.heat_pump import DEFAULT_BRINE_TEMP, HeatPump
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.simulation_runner.simulation_utils import get_local_price_if_exists_else_external_estimate

logger = logging.getLogger(__name__)


class BuildingAgent(IAgent):

    heat_pricing: HeatingPrice
    electricity_pricing: ElectricityPrice
    digital_twin: StaticDigitalTwin
    n_heat_pumps: int
    workloads_data: Dict[float, OrderedDict[int, Tuple[float, float]]]  # Keys should be strictly increasing
    allow_sell_heat: bool

    def __init__(self, heat_pricing: HeatingPrice, electricity_pricing: ElectricityPrice,
                 digital_twin: StaticDigitalTwin, nbr_heat_pumps: int = 0,
                 coeff_of_perf: Optional[float] = None, guid="BuildingAgent"):
        super().__init__(guid)
        self.heat_pricing = heat_pricing
        self.electricity_pricing = electricity_pricing
        self.digital_twin = digital_twin
        self.n_heat_pumps = nbr_heat_pumps
        self.outdoor_temperatures = None  # TODO: Temperature data
        self.temperature_pairs = create_set_of_outdoor_brine_temps_pairs(self.outdoor_temperatures)
        self.workloads_data = construct_workloads_data(list(self.temperature_pairs['brine_temp_c'])
                                                       + [DEFAULT_BRINE_TEMP],
                                                       coeff_of_perf, nbr_heat_pumps)
        self.allow_sell_heat = False

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None) -> List[GrossBid]:
        # The building should make a bid for purchasing energy, or selling if it has a surplus
        prev_period = trading_platform_utils.minus_n_hours(period, 1)
        prev_prices = get_local_price_if_exists_else_external_estimate(
            prev_period, clearing_prices_historical, [self.electricity_pricing, self.heat_pricing])
        return self.make_bids_with_heat_pump(period, prev_prices[Resource.ELECTRICITY],
                                             prev_prices[Resource.HEATING])

    def make_prognosis(self, period: datetime.datetime, resource: Resource) -> float:
        # The building should make a prognosis for how much energy will be required
        prev_trading_period = trading_platform_utils.minus_n_hours(period, 1)
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
        elec_retail_price = self.electricity_pricing.\
            get_estimated_retail_price(period, True)
        elec_wholesale_price = self.electricity_pricing.\
            get_estimated_wholesale_price(period)
        heat_retail_price = self.heat_pricing.\
            get_estimated_retail_price(period, True)
        heat_wholesale_price = self.heat_pricing.\
            get_estimated_wholesale_price(period)

        elec_net_consumption_pred = self.make_prognosis(period, Resource.ELECTRICITY)
        heat_net_consumption_pred = self.make_prognosis(period, Resource.HEATING)
        elec_clearing_price = clearing_prices[Resource.ELECTRICITY]
        heat_clearing_price = clearing_prices[Resource.HEATING]

        # Find brine temp for the closest outdoor temperature
        temp = self.outdoor_temperatures.loc[period]
        closest_row = self.temperature_pairs.iloc[(self.temperature_pairs['outdoor_temp_c'] - temp).abs().argsort()[:1]]
        brine_temp_c = closest_row['brine_temp_c'].iloc[0]

        # Re-calculate optimal workload, now that prices are known
        workload_to_use = self.calculate_optimal_workload(brine_temp_c, elec_net_consumption_pred,
                                                          heat_net_consumption_pred, elec_clearing_price,
                                                          heat_clearing_price)

        elec_needed_for_1_heat_pump = self.workloads_data[brine_temp_c][workload_to_use][0]
        heat_output_for_1_heat_pump = self.workloads_data[brine_temp_c][workload_to_use][1]

        # Now, the trading period "happens", some resources are consumed, some produced...
        elec_usage = self.get_actual_usage(period, Resource.ELECTRICITY)
        heat_usage = self.get_actual_usage(period, Resource.HEATING)
        elec_net_consumption_incl_pump = elec_usage + elec_needed_for_1_heat_pump * self.n_heat_pumps
        heat_net_consumption_incl_pump = heat_usage - heat_output_for_1_heat_pump * self.n_heat_pumps

        if elec_net_consumption_incl_pump > 0:
            # Positive net consumption, so need to buy electricity
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(elec_clearing_price,
                                                                                  elec_retail_price)
            trades.append(self.construct_elec_trade(period=period, action=Action.BUY,
                                                    quantity=elec_net_consumption_incl_pump,
                                                    price=price_to_use, market=market_to_use))
        elif elec_net_consumption_incl_pump < 0:
            # Negative net consumption, meaning there is a surplus, which the agent will sell
            price_to_use, market_to_use = get_price_and_market_to_use_when_selling(elec_clearing_price,
                                                                                   elec_wholesale_price)
            # NOTE: Here we assume that even if we sell electricity on the "external market", we still pay
            # the internal electricity tax, and the internal grid fee
            trades.append(self.construct_elec_trade(period=period, action=Action.SELL,
                                                    quantity=-elec_net_consumption_incl_pump,
                                                    price=price_to_use, market=market_to_use,
                                                    tax_paid=self.electricity_pricing.elec_tax_internal,
                                                    grid_fee_paid=self.electricity_pricing
                                                    .elec_grid_fee_internal))
        if heat_net_consumption_incl_pump > 0:
            # Positive net consumption, so need to buy heating
            price_to_use, market_to_use = get_price_and_market_to_use_when_buying(heat_clearing_price,
                                                                                  heat_retail_price)
            trades.append(self.construct_buy_heat_trade(period=period, quantity_needed=heat_net_consumption_incl_pump,
                                                        price=price_to_use, market=market_to_use,
                                                        heat_transfer_loss_per_side=self.heat_pricing
                                                        .heat_transfer_loss_per_side))
        elif heat_net_consumption_incl_pump < 0:
            # Negative net consumption, meaning there is a surplus, which the agent will sell
            if self.allow_sell_heat:
                price_to_use, market_to_use = get_price_and_market_to_use_when_selling(heat_clearing_price,
                                                                                       heat_wholesale_price)
                trades.append(self.construct_sell_heat_trade(period=period, quantity=-heat_net_consumption_incl_pump,
                                                             price=price_to_use, market=market_to_use,
                                                             heat_transfer_loss_per_side=self.heat_pricing
                                                             .heat_transfer_loss_per_side))
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

        # Find brine temp for the closest outdoor temperature
        temp = self.outdoor_temperatures.loc[period]
        closest_row = self.temperature_pairs.iloc[(self.temperature_pairs['outdoor_temp_c'] - temp).abs().argsort()[:1]]
        brine_temp_c = closest_row['brine_temp_c'].iloc[0]

        heat_net_consumption = self.make_prognosis(period, Resource.HEATING)
        elec_net_consumption = self.make_prognosis(period, Resource.ELECTRICITY)  # Negative means net production
        workload_to_use = self.calculate_optimal_workload(brine_temp_c, elec_net_consumption, heat_net_consumption,
                                                          pred_elec_price, pred_heat_price)

        elec_needed_for_1_heat_pump = self.workloads_data[brine_temp_c][workload_to_use][0]
        heat_output_for_1_heat_pump = self.workloads_data[brine_temp_c][workload_to_use][1]

        # Now we have decided what workload to use. Next, construct bids
        bids = []
        elec_net_consumption_incl_pump = elec_net_consumption + elec_needed_for_1_heat_pump * self.n_heat_pumps
        heat_net_consumption_incl_pump = heat_net_consumption - heat_output_for_1_heat_pump * self.n_heat_pumps
        if elec_net_consumption_incl_pump > 0:
            bids.append(self.construct_elec_bid(period, Action.BUY, elec_net_consumption_incl_pump, math.inf))
            # This demand must be fulfilled - therefore price is inf
        elif elec_net_consumption_incl_pump < 0:
            # What price to use here? The predicted local clearing price, or the external grid wholesale price?
            # Going with the latter
            bids.append(self.construct_elec_bid(period, Action.SELL, -elec_net_consumption_incl_pump,
                                                self.electricity_pricing.get_external_grid_buy_price(period)))
        if heat_net_consumption_incl_pump > 0:
            bids.append(self.construct_buy_heat_bid(period, heat_net_consumption_incl_pump, math.inf,
                                                    self.heat_pricing.heat_transfer_loss_per_side))
            # This demand must be fulfilled - therefore price is inf
        elif heat_net_consumption_incl_pump < 0 and self.allow_sell_heat:
            # What price to use here? The predicted local clearing price, or the external grid wholesale price?
            # External grid may not want to buy heat at all, so going with the former, for now.
            bids.append(self.construct_sell_heat_bid(period, -heat_net_consumption_incl_pump, pred_heat_price,
                                                     self.heat_pricing.heat_transfer_loss_per_side))
        return bids

    def calculate_optimal_workload(self, brine_temp_c: float, elec_net_consumption: float, heat_net_consumption: float,
                                   pred_elec_price: float, pred_heat_price: float) -> int:
        """
        Calculates the optimal workload to run the agent's heat pumps. "Optimal" is the workload which leads to the
        lowest cost - the cost stemming from the import of electricity and/or heating, minus any income from electricity
        sold.
        """
        # Gross price, since we are interested in calculating our potential profit
        elec_sell_price = self.electricity_pricing.get_electricity_gross_internal_price(pred_elec_price)
        heat_sell_price = pred_heat_price if self.allow_sell_heat else 0

        # Converting workload ordered dict into numpy array for faster computing
        # Columns: Workload, electricity input, heating output
        workload_elec_heat_array = np.array([np.array([workload, vals[0], vals[1]])
                                             for workload, vals in self.workloads_data[brine_temp_c].items()])
        elec = workload_elec_heat_array[:, 1]
        heat = workload_elec_heat_array[:, 2]

        # Calculate electricity supply and demand
        elec_net_consumption_incl_pump = elec_net_consumption + elec * self.n_heat_pumps
        elec_supply = supply(elec_net_consumption_incl_pump)
        elec_demand = demand(elec_net_consumption_incl_pump)

        # Calculate heating supply and demand
        heat_net_consumption_incl_pump = heat_net_consumption - heat * self.n_heat_pumps
        heat_supply = supply(heat_net_consumption_incl_pump)
        heat_demand = demand(heat_net_consumption_incl_pump)

        # Calculate expected cost
        incomes = elec_supply * elec_sell_price + heat_supply * heat_sell_price
        expenditures = elec_demand * pred_elec_price + heat_demand + pred_heat_price
        expected_cost = expenditures - incomes

        # Find workload for minimum expected cost
        index_of_min_cost = np.argmin(expected_cost)
        return workload_elec_heat_array[index_of_min_cost, 0]


def supply(net_consumption_incl_pump: np.ndarray) -> np.ndarray:
    """Return positive supply if consumption is negative, otherwise zero."""
    return np.absolute(np.minimum(np.zeros(len(net_consumption_incl_pump)), net_consumption_incl_pump))


def demand(net_consumption_incl_pump: np.ndarray) -> np.ndarray:
    """Return demand if consumption is positive, otherwise zero."""
    return np.maximum(np.zeros(len(net_consumption_incl_pump)), net_consumption_incl_pump)


def construct_workloads_data(brine_temps_lst: List[float], coeff_of_perf: Optional[float], n_heat_pumps: int) -> \
        Dict[float, OrderedDict]:
    """
    Will construct a dict with brine temperatures as keys, and ordered dicts as values, in which workload is key,
    and input, output are the values.
    If there are no heat pumps (n_heat_pumps = 0), the returned ordered dicts in the dict will have only one row,
    which corresponds to not running a heat pump at all.
    """
    if n_heat_pumps == 0:
        ordered_dict = OrderedDict()
        ordered_dict[0] = (0.0, 0.0)
        dct = {brine_temp_c: ordered_dict for brine_temp_c in brine_temps_lst}
        return dct
    if coeff_of_perf is None:
        return HeatPump.calculate_for_all_workloads_for_all_brine_temps(brine_temps_lst)
    return HeatPump.calculate_for_all_workloads_for_all_brine_temps(brine_temps_lst, coeff_of_perf=coeff_of_perf)
