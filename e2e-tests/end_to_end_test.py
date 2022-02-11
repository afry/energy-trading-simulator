from unittest import TestCase

from pkg_resources import resource_filename

from tradingplatformpoc import simulation_runner
from tradingplatformpoc.bid import Action
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES


class Test(TestCase):

    def test(self):
        """
        Run the trading simulations with simulation_runner. If it runs ok (and doesn't throw an error or anything), then
        this test will go through all trading periods, assert that the total amount of energy bought equals the total
        amount of energy sold. Furthermore, it will look at monetary compensation, and make sure that the amounts paid
        and received by different actors all match up.
        """
        mock_datas_file_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")

        clearing_prices, all_trades, all_extra_costs = simulation_runner.run_trading_simulations(mock_datas_file_path,
                                                                                                 "../results/")

        for period in clearing_prices.keys():
            trades_for_period = [x for x in all_trades if x.period == period]
            extra_costs_for_period = all_extra_costs[period]
            for resource in ALL_IMPLEMENTED_RESOURCES:
                trades_for_period_and_resource = [x for x in trades_for_period if x.resource == resource]
                energy_bought_kwh = sum([x.quantity for x in trades_for_period_and_resource if x.action == Action.BUY])
                energy_sold_kwh = sum([x.quantity for x in trades_for_period_and_resource if x.action == Action.SELL])
                self.assertAlmostEqual(energy_bought_kwh, energy_sold_kwh, places=7)

            total_cost = 0  # Should sum to 0 at the end of this loop
            agents_who_traded_or_were_penalized = set([x.source for x in trades_for_period] +
                                                      list(extra_costs_for_period.keys()))
            for agent in agents_who_traded_or_were_penalized:
                trades_for_agent = [x for x in trades_for_period if x.source == agent]
                extra_costs_for_agent = get_extra_cost_for_agent(extra_costs_for_period, agent)
                cost_for_agent = sum([x.get_cost_of_trade() for x in trades_for_agent]) + extra_costs_for_agent
                total_cost = total_cost + cost_for_agent
            self.assertAlmostEqual(0, total_cost)


def get_extra_cost_for_agent(extra_costs_for_period, agent):
    if agent in extra_costs_for_period:
        return extra_costs_for_period[agent]
    else:
        return 0
