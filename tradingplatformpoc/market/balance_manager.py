from typing import List, Optional, Tuple

import pandas as pd

from tradingplatformpoc.market.extra_cost import ExtraCost, ExtraCostType
from tradingplatformpoc.market.trade import Action, Resource
from tradingplatformpoc.sql.trade.crud import all_trades_for_resource_from_db


def get_external_trade(trades: List) -> Tuple[Optional[float], Optional[Action], Optional[str]]:
    external_trades = [x for x in trades if x.by_external]
    if len(external_trades) == 0:
        return None, None, None
    elif len(external_trades) > 1:
        if len(set([x.action for x in external_trades])) > 1:
            raise RuntimeError("Unexpected state: External grid both bought and sold in the same trading period")
        else:
            summed_quantity = sum([t.quantity_pre_loss for t in external_trades])
            return summed_quantity, external_trades[0].action, external_trades[0].source
    else:
        return external_trades[0].quantity_pre_loss, external_trades[0].action, external_trades[0].source


def correct_for_exact_price(trading_periods: pd.DatetimeIndex,
                            prices: pd.DataFrame, resource: Resource, extra_cost_type: ExtraCostType,
                            job_id: str, local_market_enabled: bool, block_agent_ids: List[str]) -> List[ExtraCost]:
    """
    The price of an external resource isn't known when making trades - it is only known after the month has concluded.
    If we for simplicity regard only the retail prices (external grid selling, and not buying), and we define:
        p as the "estimated" price (used at the time of the bid and the trade) in SEK/kWh
        x as the "exact" price (known at the end of the month) in SEK/kWh
        D as the total amount of the resource imported to the microgrid for the month
    The external grid will then be owed (x - p) * D SEK
    We should attribute this cost (or, if p > x, this income) based on resource usage.

    @return A list of ExtraCost entities, containing information about what period and agent the cost is for, and a
        "cost" value, where a negative value means the agent is owed money for the period, rather than owing the money
        to someone else.
    """
    if local_market_enabled:
        return correct_for_exact_price_for_lec(trading_periods, prices, resource, extra_cost_type, job_id)
    return correct_for_exact_price_no_lec(trading_periods, prices, resource, extra_cost_type, job_id, block_agent_ids)


def correct_for_exact_price_for_lec(trading_periods: pd.DatetimeIndex, prices: pd.DataFrame, resource: Resource,
                                    extra_cost_type: ExtraCostType, job_id: str) -> List[ExtraCost]:

    extra_costs: List[ExtraCost] = []
        
    all_trades_of_resource = all_trades_for_resource_from_db(job_id, resource)

    for period in trading_periods:
        if period not in list(all_trades_of_resource.keys()):
            # No trades of this resource for the period - no corrections needed
            continue

        trades_for_period = all_trades_of_resource[period]

        prices_for_period = prices[prices.period == period].iloc[0]
        exact_ext_retail_price = prices_for_period.exact_retail_price
        exact_ext_wholesale_price = prices_for_period.exact_wholesale_price
        est_ext_retail_price = prices_for_period.estimated_retail_price
        est_ext_wholesale_price = prices_for_period.estimated_wholesale_price

        ext_trade_quantity, ext_trade_action, ext_trade_source = get_external_trade(trades_for_period)
        if ext_trade_quantity is not None and ext_trade_action is not None and ext_trade_source is not None:
            if ext_trade_action == Action.SELL:
                internal_buy_trades = [x for x in trades_for_period if (not x.by_external) & (x.action == Action.BUY)]
                total_internal_usage = sum([x.quantity_pre_loss for x in internal_buy_trades])
                total_debt = (exact_ext_retail_price - est_ext_retail_price) * ext_trade_quantity

                extra_costs.append(ExtraCost(period, ext_trade_source, extra_cost_type, -total_debt))

                for internal_trade in internal_buy_trades:
                    net_usage = internal_trade.quantity_pre_loss
                    share_of_debt = net_usage / total_internal_usage
                    extra_costs.append(ExtraCost(period, internal_trade.source, extra_cost_type,
                                                 share_of_debt * total_debt))
            else:
                internal_sell_trades = [x for x in trades_for_period if (not x.by_external)
                                        & (x.action == Action.SELL)]
                total_internal_prod = sum([x.quantity_pre_loss for x in internal_sell_trades])
                total_debt = (est_ext_wholesale_price - exact_ext_wholesale_price) * ext_trade_quantity

                extra_costs.append(ExtraCost(period, ext_trade_source, extra_cost_type, -total_debt))

                for internal_trade in internal_sell_trades:
                    net_prod = internal_trade.quantity_pre_loss
                    share_of_debt = net_prod / total_internal_prod
                    extra_costs.append(ExtraCost(period, internal_trade.source, extra_cost_type,
                                                 share_of_debt * total_debt))

    return extra_costs


def correct_for_exact_price_no_lec(trading_periods: pd.DatetimeIndex,
                                   prices: pd.DataFrame,
                                   resource: Resource,
                                   extra_cost_type: ExtraCostType,
                                   job_id: str,
                                   block_agent_ids: List[str]) -> List[ExtraCost]:
    """
    Without a LEC, this calculation needs to be made separately for each agent.
    """

    extra_costs: List[ExtraCost] = []

    all_trades_of_resource = all_trades_for_resource_from_db(job_id, resource)

    for period in trading_periods:
        if period not in list(all_trades_of_resource.keys()):
            # No trades of this resource for the period - no corrections needed
            continue

        trades_for_period = all_trades_of_resource[period]
        external_grid_agent_id = [t.source for t in trades_for_period if t.by_external][0]

        prices_for_period = prices[prices.period == period]

        for agent in block_agent_ids:
            prices_for_agent = prices_for_period[prices_for_period.agent == agent].iloc[0]
            exact_ext_retail_price = prices_for_agent.exact_retail_price
            exact_ext_wholesale_price = prices_for_agent.exact_wholesale_price
            est_ext_retail_price = prices_for_agent.estimated_retail_price
            est_ext_wholesale_price = prices_for_agent.estimated_wholesale_price

            trades_for_agent = [t for t in trades_for_period if t.source == agent]

            for trade in trades_for_agent:
                if trade.action == Action.BUY:
                    total_debt = (exact_ext_retail_price - est_ext_retail_price) * trade.quantity_pre_loss
                    extra_costs.append(ExtraCost(trade.period, external_grid_agent_id, extra_cost_type, -total_debt))
                    extra_costs.append(ExtraCost(trade.period, agent, extra_cost_type, total_debt))
                else:
                    total_debt = (est_ext_wholesale_price - exact_ext_wholesale_price) * trade.quantity_pre_loss
                    extra_costs.append(ExtraCost(trade.period, external_grid_agent_id, extra_cost_type, -total_debt))
                    extra_costs.append(ExtraCost(trade.period, agent, extra_cost_type, total_debt))

    return extra_costs
