import datetime
from typing import Collection, Dict, List, Tuple, Union

import pandas as pd

from tradingplatformpoc.market.bid import Action, NetBidWithAcceptanceStatus, Resource
from tradingplatformpoc.market.extra_cost import ExtraCost, ExtraCostType, get_extra_cost_type_for_bid_inaccuracy
from tradingplatformpoc.market.trade import Trade
from tradingplatformpoc.sql.trade.crud import heat_trades_from_db_for_periods
from tradingplatformpoc.trading_platform_utils import ALL_IMPLEMENTED_RESOURCES


def calculate_penalty_costs_for_period(bids_for_period: Collection[NetBidWithAcceptanceStatus],
                                       trades_for_period: Collection[Trade], period: datetime.datetime,
                                       clearing_prices: Dict[Resource, float],
                                       external_wholesale_prices: Dict[Resource, float],
                                       local_market_enabled: bool) -> List[ExtraCost]:
    extra_costs_for_period: List[ExtraCost] = []
    if local_market_enabled:
        for resource in ALL_IMPLEMENTED_RESOURCES:
            bids_for_resource = [x for x in bids_for_period if x.resource == resource]
            trades_for_resource = [x for x in trades_for_period if x.resource == resource]
            for_resource = calculate_penalty_costs_for_period_and_resource(bids_for_resource, trades_for_resource,
                                                                           clearing_prices[resource],
                                                                           external_wholesale_prices[resource])
            # Using period and resource, create ExtraCost entities
            extra_cost_type = get_extra_cost_type_for_bid_inaccuracy(resource)
            for (agent, cost) in for_resource.items():
                extra_costs_for_period.append(ExtraCost(period, agent, extra_cost_type, cost))

    return extra_costs_for_period


def calculate_penalty_costs_for_period_and_resource(bids_for_resource: Collection[NetBidWithAcceptanceStatus],
                                                    trades_for_resource: Collection[Trade], clearing_price: float,
                                                    external_wholesale_price: float) -> Dict[str, float]:
    """
    All bids and trades should be for the same trading period.
    Sometimes, inaccurate bids lead to extra costs being created. This method attributes those extra costs to those who
    have submitted bids that are "most incorrect".
    """
    all_periods = set([x.period for x in trades_for_resource])
    if len(all_periods) > 1:
        raise RuntimeError("When calculating costs, received trades for more than 1 trading period!")
    accepted_bids = [x for x in bids_for_resource if x.accepted_quantity > 0]
    agent_ids = set([x.source for x in accepted_bids] + [x.source for x in trades_for_resource])

    external_bid = get_external_bid(bids_for_resource)
    external_trade = get_trade_by_external_grid(trades_for_resource)
    external_retail_price = external_bid.price  # Since GridAgent only places SELL-bid, this is accurate
    extra_cost = calculate_total_extra_cost_for_period(external_trade,
                                                       clearing_price,
                                                       external_wholesale_price,
                                                       external_retail_price)
    # Now we know how much extra cost that need to be covered. Now we'll figure out how to distribute it.

    error_by_agent = calculate_error_by_agent(accepted_bids, agent_ids, trades_for_resource)
    cost_to_be_paid_by_agent = distribute_cost(error_by_agent, extra_cost)
    return cost_to_be_paid_by_agent


def calculate_costs_for_heating(trading_periods: Collection[datetime.datetime],
                                all_bids: Dict[datetime.datetime, Collection[NetBidWithAcceptanceStatus]],
                                all_trades: Collection[Trade],
                                clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]],
                                est_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]) -> \
        Dict[datetime.datetime, Dict[str, float]]:
    trades = [x for x in all_trades if x.resource == Resource.HEATING]

    costs_by_period: Dict[datetime.datetime, Dict[str, float]] = {}

    # Loop through periods
    for period in trading_periods:
        bids_for_period = [x for x in all_bids[period] if x.resource == Resource.HEATING]
        trades_for_period = [x for x in trades if x.period == period]
        clearing_price = clearing_prices_historical[period][Resource.HEATING]
        est_external_wholesale_price = est_wholesale_heating_prices_by_year_and_month[(period.year, period.month)]

        costs_this_period = calculate_penalty_costs_for_period_and_resource(bids_for_period,
                                                                            trades_for_period,
                                                                            clearing_price,
                                                                            est_external_wholesale_price)
        costs_by_period[period] = costs_this_period
    return costs_by_period


def get_trade_by_external_grid(trades: Collection[Trade]) -> Union[Trade, None]:
    external_grid_operator_trades = [x for x in trades if x.by_external]
    if len(external_grid_operator_trades) == 0:
        return None
    elif len(external_grid_operator_trades) > 1:
        raise RuntimeError("Unexpected state: More than 1 external grid trade for a single trading period")
    else:
        return external_grid_operator_trades[0]


def get_external_bid(bids: Collection[NetBidWithAcceptanceStatus]) -> NetBidWithAcceptanceStatus:
    """
    From a collection of bids, gets the one which has by_external = True. If there is no such bid, or if there are more
    than one, the function throws a RuntimeError.
    """
    external_bids = [x for x in bids if x.by_external]
    if len(external_bids) != 1:
        raise RuntimeError("Expected 1 and only 1 external grid bid for a single trading period, but had {}".
                           format(len(external_bids)))
    else:
        return external_bids[0]


def calculate_total_extra_cost_for_period(external_trade: Union[Trade, None], clearing_price: float,
                                          external_wholesale_price: float, external_retail_price: float) -> float:
    """
    Calculates the total "extra cost" for a period and resource, stemming from bid inaccuracies which led to the
    external grid selling to the microgrid at a higher price than the local clearing price, or the external grid buying
    from the microgrid at a lower price than the local clearing price.

    @param external_trade: An external trade, i.e. the external grid operator either buying from, or selling to, the
        local market, for the period and resource in question. Can be None, if the local market has neither a surplus
        nor a deficit.
    @param clearing_price: The clearing price for the period and resource.
    @param external_wholesale_price: The external wholesale price for the period and resource.
    @param external_retail_price: The external retail price for the period and resource.

    @return The total extra cost which the external grid will be owed. This will presumably be divided amongst market
        participants.
    """
    if external_retail_price < clearing_price:
        raise RuntimeError("Unexpected state: External retail price ({}) < local clearing price ({})".
                           format(external_retail_price, clearing_price))

    if external_trade is None:
        return 0.0
    else:
        if external_trade.action == Action.BUY:
            external_actual_export = external_trade.quantity_post_loss
            price_difference = clearing_price - external_wholesale_price
            return external_actual_export * price_difference
        else:
            external_actual_import = external_trade.quantity_pre_loss
            price_difference = external_retail_price - clearing_price
            return external_actual_import * price_difference


def distribute_cost(error_by_agent: Dict[str, float], extra_cost: float) -> Dict[str, float]:
    """
    Proportional to the absolute error of an agent's prediction, i.e. the difference between bid quantity and actual
    consumption/production.
    """
    if extra_cost == 0.0:
        return {}
    sum_of_abs_errors = sum([abs(v) for (k, v) in error_by_agent.items()])
    perc_of_cost_to_be_paid_by_agent = {k: abs(v) / sum_of_abs_errors
                                        for (k, v) in error_by_agent.items()
                                        if v != 0}
    return {k: extra_cost * v for (k, v) in perc_of_cost_to_be_paid_by_agent.items()}


def is_agent_external(accepted_bids_for_agent: List[NetBidWithAcceptanceStatus], trades_for_agent: List[Trade]) -> bool:
    """Helper method to figure out whether an agent represents an external grid, based on bids and trades for the agent.
    """
    if len(trades_for_agent) > 0:
        if trades_for_agent[0].by_external:
            return True
    if len(accepted_bids_for_agent) > 0:
        if accepted_bids_for_agent[0].by_external:
            return True
    return False


def calculate_error_by_agent(accepted_bids: Collection[NetBidWithAcceptanceStatus], agent_ids: Collection[str],
                             trades: Collection[Trade]) -> Dict[str, float]:
    """
    The error being the difference between the projected (i.e. the bid quantity) usage and the actual usage for the
    trading period. Usage is negative if the agent is a supplier.
    """
    error_by_agent = {}
    for agent_id in agent_ids:
        accepted_bids_for_agent = [x for x in accepted_bids if x.source == agent_id]
        trades_for_agent = [x for x in trades if x.source == agent_id]
        # Want to exclude external grid agents from these calculations
        if not is_agent_external(accepted_bids_for_agent, trades_for_agent):
            bid_usage = get_bid_usage(accepted_bids_for_agent, agent_id)
            actual_usage = get_actual_usage(trades_for_agent, agent_id)
            error_by_agent[agent_id] = bid_usage - actual_usage
    return error_by_agent


def get_bid_usage(accepted_bids_for_agent: List[NetBidWithAcceptanceStatus], agent_id: str) -> float:
    """Usage is negative if the agent is a supplier of energy"""
    if len(accepted_bids_for_agent) > 1:
        raise RuntimeError("Expected max 1 bid accepted per agent and trading period, but had {} for agent '{}'".
                           format(len(accepted_bids_for_agent), agent_id))
    elif len(accepted_bids_for_agent) == 0:
        return 0
    else:
        accepted_bid = accepted_bids_for_agent[0]
        return accepted_bid.accepted_quantity if accepted_bid.action == Action.BUY else -accepted_bid.accepted_quantity


def get_actual_usage(trades_for_agent: List[Trade], agent_id: str) -> float:
    """Usage is negative if the agent is a supplier of energy"""
    if len(trades_for_agent) > 1:
        raise RuntimeError("Expected max 1 trade per agent and trading period, but had {} for agent '{}'".
                           format(len(trades_for_agent), agent_id))
    elif len(trades_for_agent) == 0:
        return 0.0
    else:
        trade = trades_for_agent[0]
        return trade.quantity_post_loss if trade.action == Action.BUY else -trade.quantity_pre_loss


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
            external_trade = get_trade_by_external_grid(heating_trades)
            if external_trade is not None:
                external_trade_quantity = external_trade.quantity_post_loss
                if external_trade.action == Action.SELL:
                    internal_buy_trades = [x for x in heating_trades if (not x.by_external) & (x.action == Action.BUY)]
                    total_internal_usage = sum([x.quantity_pre_loss for x in internal_buy_trades])
                    total_debt = (exact_ext_retail_price - est_ext_retail_price) * external_trade_quantity

                    extra_costs.append(ExtraCost(period, external_trade.source, ExtraCostType.HEAT_EXT_COST_CORR,
                                                 -total_debt))

                    for internal_trade in internal_buy_trades:
                        net_usage = internal_trade.quantity_pre_loss
                        share_of_debt = net_usage / total_internal_usage
                        extra_costs.append(ExtraCost(period, internal_trade.source, ExtraCostType.HEAT_EXT_COST_CORR,
                                                     share_of_debt * total_debt))
                else:
                    internal_sell_trades = [x for x in heating_trades if (not x.by_external)
                                            & (x.action == Action.SELL)]
                    total_internal_prod = sum([x.quantity_post_loss for x in internal_sell_trades])
                    total_debt = (est_ext_wholesale_price - exact_ext_wholesale_price) * external_trade_quantity

                    extra_costs.append(ExtraCost(period, external_trade.source, ExtraCostType.HEAT_EXT_COST_CORR,
                                                 -total_debt))

                    for internal_trade in internal_sell_trades:
                        net_prod = internal_trade.quantity_post_loss
                        share_of_debt = net_prod / total_internal_prod
                        extra_costs.append(ExtraCost(period, internal_trade.source, ExtraCostType.HEAT_EXT_COST_CORR,
                                                     share_of_debt * total_debt))

    return extra_costs
