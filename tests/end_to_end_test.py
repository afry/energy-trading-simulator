import os
from unittest import TestCase

from tradingplatformpoc import simulation_runner
from tradingplatformpoc.bid import Action


class Test(TestCase):

    def test(self):
        """
        Run the trading simulations with simulation_runner. If it runs ok (and doesn't throw an error or anything), then
        this test will go through all trading periods, assert that the total amount of energy bought equals the total
        amount of energy sold. Furthermore, it will look at monetary compensation, and make sure that the amounts paid
        and received by different actors all match up.
        """

        current_directory = os.getcwd()
        mock_datas_file_path = get_mock_datas_pickle_file_path(current_directory)

        clearing_prices, all_trades, all_extra_costs = simulation_runner.run_trading_simulations(mock_datas_file_path)

        for period in clearing_prices.keys():
            trades_for_period = [x for x in all_trades if x.period == period]
            extra_costs_for_period = all_extra_costs[period]
            elec_bought_kwh = sum([x.quantity for x in trades_for_period if x.action == Action.BUY])
            elec_sold_kwh = sum([x.quantity for x in trades_for_period if x.action == Action.SELL])
            self.assertAlmostEqual(elec_bought_kwh, elec_sold_kwh, places=7)

            total_cost = 0  # Should sum to 0 at the end of this loop
            agents_who_traded_or_were_penalized = set([x.source for x in trades_for_period] +
                                                      list(extra_costs_for_period.keys()))
            for agent in agents_who_traded_or_were_penalized:
                trades_for_agent = [x for x in trades_for_period if x.source == agent]
                extra_costs_for_agent = get_extra_cost_for_agent(extra_costs_for_period, agent)
                cost_for_agent = sum([x.get_cost_of_trade() for x in trades_for_agent]) + extra_costs_for_agent
                total_cost = total_cost + cost_for_agent
            self.assertAlmostEqual(0, total_cost)


def get_mock_datas_pickle_file_path(current_directory):
    folders = current_directory.split("\\")
    if folders[len(folders) - 1] == 'trading-platform-poc':
        mock_datas_file_path = './tradingplatformpoc/data/generated/mock_datas.pickle'
    elif folders[len(folders) - 2] == 'trading-platform-poc':
        mock_datas_file_path = '../tradingplatformpoc/data/generated/mock_datas.pickle'
    else:
        raise RuntimeError('Could not find pickle file with mock data')
    return mock_datas_file_path


def get_extra_cost_for_agent(extra_costs_for_period, agent):
    if agent in extra_costs_for_period:
        return extra_costs_for_period[agent]
    else:
        return 0
