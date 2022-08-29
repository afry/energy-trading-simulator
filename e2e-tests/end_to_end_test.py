import json
from unittest import TestCase

from pkg_resources import resource_filename

from tradingplatformpoc import simulation_runner
from tradingplatformpoc.bid import Action
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES

mock_datas_file_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
config_filename = resource_filename("tradingplatformpoc.data", "default_config.json")
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

        simulation_results = simulation_runner.run_trading_simulations(config_data, mock_datas_file_path)

        for period in simulation_results.clearing_prices_historical.keys():
            trades_for_period = simulation_results.all_trades.loc[simulation_results.all_trades.period == period]
            extra_costs_for_period = simulation_results.all_extra_costs.loc[simulation_results.all_extra_costs.period
                                                                            == period]
            for resource in ALL_IMPLEMENTED_RESOURCES:
                trades_for_period_and_resource = trades_for_period.loc[trades_for_period.resource == resource]
                energy_bought_kwh = sum(trades_for_period_and_resource.loc[trades_for_period_and_resource.action ==
                                                                           Action.BUY, 'quantity_pre_loss'])
                energy_sold_kwh = sum(trades_for_period_and_resource.loc[trades_for_period_and_resource.action ==
                                                                         Action.SELL, 'quantity_post_loss'])
                self.assertAlmostEqual(energy_bought_kwh, energy_sold_kwh, places=7)

            total_cost = 0  # Should sum to 0 at the end of this loop
            agents_who_traded_or_were_penalized = set(trades_for_period.source.tolist() +
                                                      extra_costs_for_period.agent.tolist())
            for agent_id in agents_who_traded_or_were_penalized:
                trades_for_agent = trades_for_period.loc[trades_for_period.source == agent_id]
                extra_costs_for_agent = extra_costs_for_period.loc[extra_costs_for_period.agent == agent_id]
                cost_for_agent = sum(get_costs_of_trades_for_agent(trades_for_agent)) + extra_costs_for_agent.cost.sum()
                total_cost = total_cost + cost_for_agent
            self.assertAlmostEqual(0, total_cost)


def get_costs_of_trades_for_agent(trades_for_agent):
    return trades_for_agent.apply(lambda x: x.get_cost_of_trade(), axis=1)
