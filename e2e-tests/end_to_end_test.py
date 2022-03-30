import json
from typing import List
from unittest import TestCase

from pkg_resources import resource_filename

from tradingplatformpoc import simulation_runner
from tradingplatformpoc.bid import Action
from tradingplatformpoc.extra_cost import ExtraCost
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES

mock_datas_file_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
config_filename = resource_filename("tradingplatformpoc.data", "default_config.json")
results_path = "../results/"
with open(config_filename, "r") as jsonfile:
    config_data = json.load(jsonfile)


class Test(TestCase):

    def test(self):
        """
        Run the trading simulations with simulation_runner. If it runs ok (and doesn't throw an error or anything), then
        this test will go through all trading periods, assert that the total amount of energy bought equals the total
        amount of energy sold. Furthermore, it will look at monetary compensation, and make sure that the amounts paid
        and received by different actors all match up.
        """

        simulation_results = simulation_runner.run_trading_simulations(config_data, mock_datas_file_path, results_path)

        for period in simulation_results.clearing_prices_historical.keys():
            trades_for_period = simulation_results.all_trades.loc[simulation_results.all_trades.period == period]
            extra_costs_for_period = [ec for ec in simulation_results.all_extra_costs if (ec.period == period)]
            for resource in ALL_IMPLEMENTED_RESOURCES:
                trades_for_period_and_resource = trades_for_period.loc[trades_for_period.resource == resource]
                energy_bought_kwh = sum(trades_for_period_and_resource.loc[trades_for_period_and_resource.action ==
                                                                           Action.BUY, 'quantity'])
                energy_sold_kwh = sum(trades_for_period_and_resource.loc[trades_for_period_and_resource.action ==
                                                                         Action.SELL, 'quantity'])
                self.assertAlmostEqual(energy_bought_kwh, energy_sold_kwh, places=7)

            total_cost = 0  # Should sum to 0 at the end of this loop
            agents_who_traded_or_were_penalized = set(trades_for_period.source.tolist() +
                                                      [x.agent for x in extra_costs_for_period])
            for agent_id in agents_who_traded_or_were_penalized:
                trades_for_agent = trades_for_period.loc[trades_for_period.source == agent_id]
                extra_costs_for_agent = get_extra_cost_for_agent(extra_costs_for_period, agent_id)
                cost_for_agent = sum(trades_for_agent.apply(lambda x: get_cost_of_trade(x.action, x.quantity, x.price),
                                                            axis=1)) + extra_costs_for_agent
                total_cost = total_cost + cost_for_agent
            self.assertAlmostEqual(0, total_cost)


def get_extra_cost_for_agent(extra_costs_for_period: List[ExtraCost], agent_id: str) -> float:
    return sum([ec.cost for ec in extra_costs_for_period if (ec.agent == agent_id)])


def get_cost_of_trade(action: Action, quantity: float, price: float) -> float:
    """Negative if it is an income, i.e. if the trade is a SELL"""
    if action == Action.BUY:
        return quantity * price
    else:
        return -quantity * price
