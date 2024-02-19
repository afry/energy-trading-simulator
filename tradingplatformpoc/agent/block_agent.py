import datetime
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from tradingplatformpoc import trading_platform_utils
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.digitaltwin.battery import Battery
from tradingplatformpoc.digitaltwin.heat_pump import HIGH_HEAT_FORWARD_TEMP, LOW_HEAT_FORWARD_TEMP, MAX_INPUT, \
    MAX_OUTPUT, Workloads
from tradingplatformpoc.digitaltwin.static_digital_twin import StaticDigitalTwin
from tradingplatformpoc.market.bid import Action, GrossBid, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.trade import Trade, TradeMetadataKey
from tradingplatformpoc.price.electricity_price import ElectricityPrice
from tradingplatformpoc.price.heating_price import HeatingPrice
from tradingplatformpoc.simulation_runner.simulation_utils import get_local_price_if_exists_else_external_estimate

logger = logging.getLogger(__name__)


class BlockAgent(IAgent):

    heat_pricing: HeatingPrice
    electricity_pricing: ElectricityPrice
    digital_twin: StaticDigitalTwin
    workloads_high_heat: Workloads
    workloads_low_heat: Workloads
    battery: Battery
    allow_sell_heat: bool
    heat_pump_max_input: float
    heat_pump_max_output: float
    # Our heat pump implementation is built on "Thermia Mega" heat pumps - we translate the "max power" and "max heat"
    # into an estimated number of those.
    n_heat_pumps: float

    def __init__(self, local_market_enabled: bool, heat_pricing: HeatingPrice, electricity_pricing: ElectricityPrice,
                 digital_twin: StaticDigitalTwin, heat_pump_max_input: float = 0, heat_pump_max_output: float = 0,
                 coeff_of_perf: Optional[float] = None, battery: Optional[Battery] = None, guid="BlockAgent"):
        super().__init__(guid, local_market_enabled)
        self.heat_pricing = heat_pricing
        self.electricity_pricing = electricity_pricing
        self.digital_twin = digital_twin
        self.heat_pump_max_input = heat_pump_max_input
        self.heat_pump_max_output = heat_pump_max_output
        self.allow_sell_heat = False
        self.battery = Battery(0, 0, 0, 0) if battery is None else battery
        # Calculate an implied number of Thermia Mega Normal size heat pumps, taking both input and output power into
        # account
        self.n_heat_pumps = ((heat_pump_max_input / MAX_INPUT) + (heat_pump_max_output / MAX_OUTPUT)) / 2
        any_heat_pumps = (heat_pump_max_input > 0) and (heat_pump_max_output > 0)
        self.workloads_high_heat = Workloads(coeff_of_perf, any_heat_pumps, HIGH_HEAT_FORWARD_TEMP)
        self.workloads_low_heat = Workloads(coeff_of_perf, any_heat_pumps, LOW_HEAT_FORWARD_TEMP)

    def make_bids(self, period: datetime.datetime, clearing_prices_historical: Union[Dict[datetime.datetime, Dict[
            Resource, float]], None] = None) -> List[GrossBid]:
        # The agent should make a bid for purchasing energy, or selling if it has a surplus
        prev_period = trading_platform_utils.minus_n_hours(period, 1)
        prev_prices = get_local_price_if_exists_else_external_estimate(
            prev_period, clearing_prices_historical, [self.electricity_pricing, self.heat_pricing])
        return self.make_bids_with_heat_pump(period, prev_prices[Resource.ELECTRICITY],
                                             prev_prices[Resource.HEATING])

    def make_prognosis(self, period: datetime.datetime, resource: Resource) -> float:
        # The agent should make a prognosis for how much energy will be required
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

        # TODO: Get demand of low- and high-heat, figure out what can be bought on the local market, and what we'll have
        #  to generate ourselves
        elec_net_consumption_pred = self.make_prognosis(period, Resource.ELECTRICITY)
        heat_net_consumption_pred = self.make_prognosis(period, Resource.HEATING)
        elec_clearing_price = clearing_prices[Resource.ELECTRICITY]
        heat_clearing_price = clearing_prices[Resource.HEATING]
        elec_sell_price, elec_buy_price = self.calculate_electricity_prices(elec_clearing_price, period)
        heat_sell_price, heat_buy_price = self.calculate_heating_prices(heat_clearing_price, period)
        # Re-calculate optimal workload, now that prices are known
        workload_to_use, elec_needed_for_1_heat_pump, heat_output_for_1_heat_pump = \
            self.calculate_optimal_workload(elec_net_consumption_pred, heat_net_consumption_pred, elec_sell_price,
                                            elec_buy_price, heat_sell_price, heat_buy_price)

        # Now, the trading period "happens", some resources are consumed, some produced...
        elec_usage = self.get_actual_usage(period, Resource.ELECTRICITY)
        heat_usage = self.get_actual_usage(period, Resource.HEATING)
        elec_net_consumption_incl_pump = elec_usage + elec_needed_for_1_heat_pump * self.n_heat_pumps
        heat_net_consumption_incl_pump = heat_usage - heat_output_for_1_heat_pump * self.n_heat_pumps

        if elec_net_consumption_incl_pump > 0:
            # Positive net consumption, so need to buy electricity
            price_to_use, market_to_use = self.get_price_and_market_to_use_when_buying(
                elec_clearing_price, elec_retail_price)
            trades.append(self.construct_elec_trade(period=period, action=Action.BUY,
                                                    quantity=elec_net_consumption_incl_pump,
                                                    price=price_to_use, market=market_to_use))
        elif elec_net_consumption_incl_pump < 0:
            # Negative net consumption, meaning there is a surplus, which the agent will sell
            price_to_use, market_to_use = self.get_price_and_market_to_use_when_selling(
                elec_clearing_price, elec_wholesale_price)
            tax = self.electricity_pricing.get_tax(market_to_use)
            grid_fee = self.electricity_pricing.get_grid_fee(market_to_use)
            trades.append(self.construct_elec_trade(period=period, action=Action.SELL,
                                                    quantity=-elec_net_consumption_incl_pump,
                                                    price=price_to_use, market=market_to_use,
                                                    tax_paid=tax,
                                                    grid_fee_paid=grid_fee))
        if heat_net_consumption_incl_pump > 0:
            # Positive net consumption, so need to buy heating
            price_to_use, market_to_use = self.get_price_and_market_to_use_when_buying(
                heat_clearing_price, heat_retail_price)
            trades.append(self.construct_buy_heat_trade(period=period, quantity_needed=heat_net_consumption_incl_pump,
                                                        price=price_to_use, market=market_to_use,
                                                        heat_transfer_loss_per_side=self.heat_pricing
                                                        .heat_transfer_loss_per_side))
        elif heat_net_consumption_incl_pump < 0:
            # Negative net consumption, meaning there is a surplus, which the agent will sell
            if self.allow_sell_heat:
                price_to_use, market_to_use = self.get_price_and_market_to_use_when_selling(
                    heat_clearing_price, heat_wholesale_price)
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

        # TODO: Get demand of low- and high-heat, figure out what can be bought on the local market, and what we'll have
        #  to generate ourselves

        heat_net_consumption = self.make_prognosis(period, Resource.HEATING)
        elec_net_consumption = self.make_prognosis(period, Resource.ELECTRICITY)  # Negative means net production
        elec_sell_price, elec_buy_price = self.calculate_electricity_prices(pred_elec_price, period)
        heat_sell_price, heat_buy_price = self.calculate_heating_prices(pred_heat_price, period)
        workload_to_use, elec_needed_for_1_heat_pump, heat_output_for_1_heat_pump = \
            self.calculate_optimal_workload(elec_net_consumption, heat_net_consumption, elec_sell_price,
                                            elec_buy_price, heat_sell_price, heat_buy_price)

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

    def calculate_optimal_workload(self, elec_net_consumption: float, heat_net_consumption: float,
                                   elec_sell_price: float, elec_buy_price: float, heat_sell_price: float,
                                   heat_buy_price: float) -> np.ndarray:
        """
        Calculates the optimal workload to run the agent's heat pumps. "Optimal" is the workload which leads to the
        lowest cost - the cost stemming from the import of electricity and/or heating, minus any income from electricity
        sold.
        """
        # TODO: Probably also calculate whether to generate high- or low-tempered heat

        # Columns: Workload, electricity input, heating output
        elec = self.workloads_high_heat.get_electricity_in_for_workloads()
        heat = self.workloads_high_heat.get_heating_out_for_workloads()

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
        expenditures = elec_demand * elec_buy_price + heat_demand * heat_buy_price
        expected_cost = expenditures - incomes

        # Find workload for minimum expected cost
        index_of_min_cost = np.argmin(expected_cost)
        return self.workloads_high_heat.get_workloads_data_from_index(index_of_min_cost)

    def calculate_electricity_prices(self, clearing_price: float, period: datetime.datetime) -> Tuple[float, float]:
        if self.local_market_enabled:
            # The seller pays taxes and grid fees (if they apply), so for the sell price, we need to deduct those from
            # the clearing price (since we are interested in calculating our potential profit)
            elec_sell_price = self.electricity_pricing.get_electricity_gross_internal_price(clearing_price)
            elec_buy_price = clearing_price
        else:
            elec_sell_price = self.electricity_pricing.get_exact_wholesale_price(period)
            elec_buy_price = self.electricity_pricing.get_exact_retail_price(period, True)
        return elec_sell_price, elec_buy_price

    def calculate_heating_prices(self, clearing_price: float, period: datetime.datetime) \
            -> Tuple[float, float]:
        if self.local_market_enabled:
            # No taxes or grid fees for heating
            heat_sell_price = clearing_price if self.allow_sell_heat else 0
            heat_buy_price = clearing_price
        else:
            heat_sell_price = self.heat_pricing.get_estimated_wholesale_price(period) if self.allow_sell_heat else 0
            heat_buy_price = self.heat_pricing.get_estimated_retail_price(period, True)
        return heat_sell_price, heat_buy_price


def supply(net_consumption_incl_pump: np.ndarray) -> np.ndarray:
    """Return positive supply if consumption is negative, otherwise zero."""
    return np.absolute(np.minimum(np.zeros(len(net_consumption_incl_pump)), net_consumption_incl_pump))


def demand(net_consumption_incl_pump: np.ndarray) -> np.ndarray:
    """Return demand if consumption is positive, otherwise zero."""
    return np.maximum(np.zeros(len(net_consumption_incl_pump)), net_consumption_incl_pump)
