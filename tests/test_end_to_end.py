import os
import unittest
from pathlib import Path
from unittest import TestCase, mock

from dotenv import load_dotenv

from tradingplatformpoc.market.trade import Action, Resource
from tradingplatformpoc.sql.job.crud import create_job_if_new_config

dotenv_path = Path('.env')
load_dotenv(dotenv_path=dotenv_path)


# TODO: Make this work with imports at top and setUp, tearDown methods
class TestEndToEnd(TestCase):

    @unittest.skipUnless(os.getenv('RUN_END_TO_END_TEST', 'False').lower() in ('true', '1', 't'),
                         reason="Lengthy test with db connection")
    def test(self):
        """
        Run the trading simulations with simulation_runner. If it runs ok (and doesn't throw an error or anything), then
        this test will go through all trading periods, assert that the total amount of energy bought equals the total
        amount of energy sold. Furthermore, it will look at monetary compensation, and make sure that the amounts paid
        and received by different actors all match up.
        """
        with mock.patch.dict(os.environ, {"PG_DATABASE": os.getenv("PG_DATABASE_TEST")}):
            from tradingplatformpoc.config.access_config import read_config
            from tradingplatformpoc.database import create_db_and_tables, drop_db_and_tables
            from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator
            from tradingplatformpoc.sql.config.crud import create_config_if_not_in_db
            from tradingplatformpoc.sql.extra_cost.crud import db_to_extra_cost_df
            from tradingplatformpoc.sql.job.crud import delete_job
            from tradingplatformpoc.sql.trade.crud import db_to_trade_df

        config_data = read_config()

        create_db_and_tables()
        try:
            create_config_if_not_in_db(config_data, 'end_to_end_config_id', 'Default setup')
            job_id = create_job_if_new_config('end_to_end_config_id')
            simulator = TradingSimulator(job_id)
            simulator()

            all_trades = db_to_trade_df(job_id)
            all_extra_costs = db_to_extra_cost_df(job_id)

            for period in all_trades['period'].unique():
                trades_for_period = all_trades.loc[all_trades.period == period]
                extra_costs_for_period = all_extra_costs.loc[all_extra_costs.period == period]
                for resource in Resource:
                    trades_for_period_and_resource = trades_for_period.loc[trades_for_period.resource == resource]
                    energy_bought_kwh = sum(trades_for_period_and_resource.loc[trades_for_period_and_resource.action
                                                                               == Action.BUY, 'quantity_pre_loss'])
                    energy_sold_kwh = sum(trades_for_period_and_resource.loc[trades_for_period_and_resource.action
                                                                             == Action.SELL, 'quantity_post_loss'])
                    self.assertAlmostEqual(energy_bought_kwh, energy_sold_kwh, places=7)

                total_cost = 0  # Should sum to 0 at the end of this loop
                agents_who_traded_or_were_penalized = set(trades_for_period.source.tolist()
                                                          + extra_costs_for_period.agent.tolist())
                for agent_id in agents_who_traded_or_were_penalized:
                    trades_for_agent = trades_for_period.loc[trades_for_period.source == agent_id]
                    extra_costs_for_agent = extra_costs_for_period.loc[extra_costs_for_period.agent == agent_id]
                    cost_for_agent = sum(get_costs_of_trades_for_agent(trades_for_agent)) \
                        + extra_costs_for_agent.cost.sum()
                    total_cost = total_cost + cost_for_agent
                self.assertAlmostEqual(0, total_cost)
            
            delete_job(job_id)
        except Exception:
            raise
        finally:
            drop_db_and_tables()


def get_costs_of_trades_for_agent(trades_for_agent):
    return trades_for_agent.apply(lambda x: get_cost_of_trade(x.action, x.quantity_pre_loss, x.price), axis=1)


def get_cost_of_trade(action: Action, quantity_pre_loss: float, price: float) -> float:
    """
    Negative if it is an income, i.e. if the trade is a SELL.
    Costs are calculated on the quantity before losses (see objective function in Chalmers' code).
    """
    if action == Action.BUY:
        return quantity_pre_loss * price
    elif action == Action.SELL:
        return -quantity_pre_loss * price
    else:
        raise RuntimeError('Unrecognized action: ' + action.name)
