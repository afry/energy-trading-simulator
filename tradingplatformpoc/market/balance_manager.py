from typing import List, Optional, Tuple

import pandas as pd

from tradingplatformpoc.market.extra_cost import ExtraCost, ExtraCostType
from tradingplatformpoc.market.trade import Action, Trade
from tradingplatformpoc.sql.trade.crud import heat_trades_from_db_for_periods


def get_external_heat_trade(trades: List[Trade]) -> Tuple[Optional[float], Optional[Action], Optional[str]]:
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


def correct_for_exact_heating_price(trading_periods: pd.DatetimeIndex,
                                    heating_prices: pd.DataFrame, job_id: str) -> List[ExtraCost]:
    """
    The price of external heating isn't known when making trades - it is only known after the month has concluded.
    If we for simplicity regard only the retail prices (external grid selling, and not buying), and we define:
        p as the "estimated" heating price (used at the time of the bid and the trade) in SEK/kWh
        x as the "exact" heating price (known at the end of the month) in SEK/kWh
        D as the total amount of district heating imported to the microgrid for the month
    The external heating grid will then be owed (x - p) * D SEK
    We should attribute this cost (or, if p > x, this income) based on district heating usage.
    For more on how we attribute this cost/income, see https://doc.afdrift.se/pages/viewpage.action?pageId=34766880

    @return A list of ExtraCost entities, containing information about what period and agent the cost is for, the
        "ExtraCostType" always being equal to "HEAT_EXT_COST_CORR", and a "cost" value, where a negative value means the
        agent is owed money for the period, rather than owing the money to someone else.
    """

    extra_costs: List[ExtraCost] = []
    for year, month in pd.unique(trading_periods.map(lambda x: (x.year, x.month))):

        # Periods
        trading_periods_in_this_month = trading_periods[(trading_periods.year == year)
                                                        & (trading_periods.month == month)]
        heating_prices_for_year_and_month = heating_prices[(heating_prices.month == month)
                                                           & (heating_prices.year == year)].iloc[0]
        exact_ext_retail_price = heating_prices_for_year_and_month.exact_retail_price
        exact_ext_wholesale_price = heating_prices_for_year_and_month.exact_wholesale_price
        est_ext_retail_price = heating_prices_for_year_and_month.estimated_retail_price
        est_ext_wholesale_price = heating_prices_for_year_and_month.estimated_wholesale_price
        
        heating_trades_for_month = heat_trades_from_db_for_periods(trading_periods_in_this_month, job_id)

        for period in trading_periods_in_this_month:
            # TODO: Can we have periods with no heating trades?
            if period not in list(heating_trades_for_month.keys()):
                heating_trades = []
            else:
                heating_trades = heating_trades_for_month[period]
            ext_trade_quantity, ext_trade_action, ext_trade_source = get_external_heat_trade(heating_trades)
            if ext_trade_quantity is not None and ext_trade_action is not None and ext_trade_source is not None:
                if ext_trade_action == Action.SELL:
                    internal_buy_trades = [x for x in heating_trades if (not x.by_external) & (x.action == Action.BUY)]
                    total_internal_usage = sum([x.quantity_pre_loss for x in internal_buy_trades])
                    total_debt = (exact_ext_retail_price - est_ext_retail_price) * ext_trade_quantity

                    extra_costs.append(ExtraCost(period, ext_trade_source, ExtraCostType.HEAT_EXT_COST_CORR,
                                                 -total_debt))

                    for internal_trade in internal_buy_trades:
                        net_usage = internal_trade.quantity_pre_loss
                        share_of_debt = net_usage / total_internal_usage
                        extra_costs.append(ExtraCost(period, internal_trade.source, ExtraCostType.HEAT_EXT_COST_CORR,
                                                     share_of_debt * total_debt))
                else:
                    internal_sell_trades = [x for x in heating_trades if (not x.by_external)
                                            & (x.action == Action.SELL)]
                    total_internal_prod = sum([x.quantity_pre_loss for x in internal_sell_trades])
                    total_debt = (est_ext_wholesale_price - exact_ext_wholesale_price) * ext_trade_quantity

                    extra_costs.append(ExtraCost(period, ext_trade_source, ExtraCostType.HEAT_EXT_COST_CORR,
                                                 -total_debt))

                    for internal_trade in internal_sell_trades:
                        net_prod = internal_trade.quantity_pre_loss
                        share_of_debt = net_prod / total_internal_prod
                        extra_costs.append(ExtraCost(period, internal_trade.source, ExtraCostType.HEAT_EXT_COST_CORR,
                                                     share_of_debt * total_debt))

    return extra_costs
