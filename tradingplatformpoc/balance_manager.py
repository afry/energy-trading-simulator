import datetime
from typing import Collection, Dict, List, Tuple, Union

from tradingplatformpoc.bid import Action, BidWithAcceptanceStatus, Resource
from tradingplatformpoc.trade import Market, Trade


def calculate_penalty_costs_for_electricity(bids: Collection[BidWithAcceptanceStatus], trades: Collection[Trade],
                                            clearing_price: float, external_wholesale_price: float) -> Dict[str, float]:
    """
    All bids and trades should be for the same trading period.
    Sometimes, inaccurate bids lead to extra costs being created. This method attributes those extra costs to those who
    have submitted bids that are "most incorrect".
    """
    bids_for_resource = [x for x in bids if x.resource == Resource.ELECTRICITY]
    trades_for_resource = [x for x in trades if x.resource == Resource.ELECTRICITY]
    all_periods = set([x.period for x in trades_for_resource])
    if len(all_periods) > 1:
        raise RuntimeError("When calculating costs, received trades for more than 1 trading period!")
    accepted_bids = [x for x in bids_for_resource if x.was_accepted]
    agent_ids = set([x.source for x in accepted_bids] + [x.source for x in trades_for_resource])

    external_bid = get_external_bid(bids_for_resource)
    external_trade_on_local_market = get_external_trade_on_local_market(trades_for_resource)
    extra_cost = calculate_total_extra_cost_for_period(external_trade_on_local_market, clearing_price,
                                                       external_wholesale_price, external_bid.price)
    # Now we know how much extra cost that need to be covered. Now we'll figure out how to distribute it.

    error_by_agent = calculate_error_by_agent(accepted_bids, agent_ids, trades_for_resource)
    cost_to_be_paid_by_agent = distribute_cost(error_by_agent, extra_cost)
    return cost_to_be_paid_by_agent


def calculate_costs_for_heating(trading_periods: Collection[datetime.datetime],
                                agent_ids: Collection[str],
                                all_bids: Dict[datetime.datetime, Collection[BidWithAcceptanceStatus]],
                                all_trades: Collection[Trade],
                                clearing_prices_historical: Dict[datetime.datetime, Dict[Resource, float]],
                                exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]) -> \
        Dict[datetime.datetime, Dict[str, float]]:
    trades = [x for x in all_trades if x.resource == Resource.HEATING]

    costs_by_period: Dict[datetime.datetime, Dict[str, float]] = {}

    # Loop through periods
    for period in trading_periods:
        bids_for_period = [x for x in all_bids[period] if (x.resource == Resource.HEATING) & x.was_accepted]
        trades_for_period = [x for x in trades if x.period == period]
        clearing_price = clearing_prices_historical[period][Resource.HEATING]
        external_wholesale_price = exact_wholesale_heating_prices_by_year_and_month[(period.year, period.month)]
        external_retail_price = exact_retail_heating_prices_by_year_and_month[(period.year, period.month)]

        external_trade_on_local_market = get_external_trade_on_local_market(trades_for_period)
        extra_cost = calculate_total_extra_cost_for_period(external_trade_on_local_market, clearing_price,
                                                           external_wholesale_price, external_retail_price)
        # Now we know how much extra cost that need to be covered. Now we'll figure out how to distribute it.
        error_by_agent = calculate_error_by_agent(bids_for_period, agent_ids, trades_for_period)
        costs_by_period[period] = distribute_cost(error_by_agent, extra_cost)
    return costs_by_period


def get_external_trade_on_local_market(trades: Collection[Trade]) -> Union[Trade, None]:
    external_trades_on_local_market = [x for x in trades if x.by_external and x.market == Market.LOCAL]
    if len(external_trades_on_local_market) == 0:
        return None
    elif len(external_trades_on_local_market) > 1:
        raise RuntimeError("Unexpected state: More than 1 external grid trade for a single trading period")
    else:
        return external_trades_on_local_market[0]


def get_external_bid(bids: Collection[BidWithAcceptanceStatus]) -> BidWithAcceptanceStatus:
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
    if external_retail_price < clearing_price:
        raise RuntimeError("Unexpected state: External retail price ({}) < local clearing price ({})".
                           format(external_retail_price, clearing_price))

    if external_trade is None:
        return 0.0
    else:
        if external_trade.action == Action.BUY:
            external_actual_export = external_trade.quantity
            price_difference = clearing_price - external_wholesale_price
            return external_actual_export * price_difference
        else:
            external_actual_import = external_trade.quantity
            price_difference = external_retail_price - clearing_price
            return external_actual_import * price_difference


def distribute_cost(error_by_agent, extra_cost) -> Dict[str, float]:
    """
    Proportional to the absolute error of an agent's prediction, i.e. the difference between bid quantity and actual
    consumption/production.
    """
    if extra_cost == 0.0:
        return {k: 0 for (k, v) in error_by_agent.items()}
    sum_of_abs_errors = sum([abs(v) for (k, v) in error_by_agent.items()])
    perc_of_cost_to_be_paid_by_agent = {k: abs(v) / sum_of_abs_errors for (k, v) in error_by_agent.items()}
    return {k: extra_cost * v for (k, v) in perc_of_cost_to_be_paid_by_agent.items()}


def is_agent_external(accepted_bids_for_agent: List[BidWithAcceptanceStatus], trades_for_agent: List[Trade]) -> bool:
    """Helper method to figure out whether an agent represents an external grid, based on bids and trades for the agent.
    """
    if len(trades_for_agent) > 0:
        if trades_for_agent[0].by_external:
            return True
    if len(accepted_bids_for_agent) > 0:
        if accepted_bids_for_agent[0].by_external:
            return True
    return False


def calculate_error_by_agent(accepted_bids: Collection[BidWithAcceptanceStatus], agent_ids: Collection[str],
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


def get_bid_usage(accepted_bids_for_agent: List[BidWithAcceptanceStatus], agent_id: str) -> float:
    """Usage is negative if the agent is a supplier of energy"""
    if len(accepted_bids_for_agent) > 1:
        raise RuntimeError("Expected max 1 bid accepted per agent and trading period, but had {} for agent '{}'".
                           format(len(accepted_bids_for_agent), agent_id))
    elif len(accepted_bids_for_agent) == 0:
        return 0
    else:
        accepted_bid = accepted_bids_for_agent[0]
        return accepted_bid.quantity if accepted_bid.action == Action.BUY else -accepted_bid.quantity


def get_actual_usage(trades_for_agent: List[Trade], agent_id: str) -> float:
    """Usage is negative if the agent is a supplier of energy"""
    if len(trades_for_agent) > 1:
        raise RuntimeError("Expected max 1 trade per agent and trading period, but had {} for agent '{}'".
                           format(len(trades_for_agent), agent_id))
    elif len(trades_for_agent) == 0:
        return 0.0
    else:
        trade = trades_for_agent[0]
        return trade.quantity if trade.action == Action.BUY else -trade.quantity


def correct_for_exact_heating_price(trading_periods: Collection[datetime.datetime], all_trades_list: List[Trade],
                                    exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                    exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                    estimated_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                    estimated_wholesale_heating_prices_by_year_and_month: Dict[
                                        Tuple[int, int], float]) -> \
        Dict[datetime.datetime, Dict[str, float]]:
    """
    The price of external heating isn't known when making trades - it is only known after the month has concluded.
    If we for simplicity regard only the retail prices (external grid selling, and not buying), and we define:
        p as the "estimated" heating price (used at the time of the bid and the trade) in SEK/kWh
        x as the "exact" heating price (known at the end of the month) in SEK/kWh
        D as the total amount of district heating imported to the microgrid for the month
    The external heating grid will then be owed (x - p) * D SEK
    We should attribute this cost (or, if p > x, this income) based on district heating usage.
    For more on how we attribute this cost/income, see https://doc.afdrift.se/pages/viewpage.action?pageId=34766880

    @return A dict where the keys are trading periods, and the values are dicts. These dicts, in turn, have agent IDs as
        keys, and "costs" (as floats) as values. Here, a negative value means the agent is owed money for the period,
        rather than owing the money to someone else.
    """

    costs_per_period_and_agent: Dict[datetime.datetime, Dict[str, float]] = {}
    heating_trades = [trade for trade in all_trades_list if trade.resource == Resource.HEATING]

    for period in trading_periods:
        dict_for_this_period: Dict[str, float] = {}

        trades_for_period = [trade for trade in heating_trades if trade.period == period]
        external_trade = get_external_trade_on_local_market(trades_for_period)
        if external_trade is not None:
            exact_ext_retail_price = exact_retail_heating_prices_by_year_and_month[(period.year, period.month)]
            exact_ext_wholesale_price = exact_wholesale_heating_prices_by_year_and_month[(period.year, period.month)]
            est_ext_retail_price = estimated_retail_heating_prices_by_year_and_month[(period.year, period.month)]
            est_ext_wholesale_price = estimated_wholesale_heating_prices_by_year_and_month[(period.year, period.month)]
            external_trade_quantity = external_trade.quantity
            if external_trade.action == Action.SELL:
                internal_buy_trades = [x for x in trades_for_period if (not x.by_external) & (x.action == Action.BUY)]
                total_internal_usage = sum([x.quantity for x in internal_buy_trades])
                total_debt = (exact_ext_retail_price - est_ext_retail_price) * external_trade_quantity
                dict_for_this_period[external_trade.source] = -total_debt
                for internal_trade in internal_buy_trades:
                    if internal_trade.price != est_ext_retail_price:
                        raise RuntimeError("External grid sold, so local market price should have been equal to "
                                           "estimated external retail price ({} SEK/kWh), but it was {} SEK/kWh. "
                                           "Period {}".format(est_ext_retail_price, internal_trade.price,
                                                              period))
                    net_usage = internal_trade.quantity
                    share_of_debt = net_usage / total_internal_usage
                    dict_for_this_period[internal_trade.source] = share_of_debt * total_debt
            else:
                internal_sell_trades = [x for x in trades_for_period if (not x.by_external) & (x.action == Action.SELL)]
                total_internal_prod = sum([x.quantity for x in internal_sell_trades])
                total_debt = (est_ext_wholesale_price - exact_ext_wholesale_price) * external_trade_quantity
                dict_for_this_period[external_trade.source] = -total_debt
                for internal_trade in internal_sell_trades:
                    if internal_trade.price != est_ext_wholesale_price:
                        raise RuntimeError("External grid bought, so local market price should have been equal to "
                                           "estimated external wholesale price ({} SEK/kWh), but it was {} SEK/kWh. "
                                           "Period {}".format(est_ext_wholesale_price, internal_trade.price,
                                                              period))
                    net_prod = internal_trade.quantity
                    share_of_debt = net_prod / total_internal_prod
                    dict_for_this_period[internal_trade.source] = share_of_debt * total_debt
        costs_per_period_and_agent[period] = dict_for_this_period

    return costs_per_period_and_agent
