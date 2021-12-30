from tradingplatformpoc.bid import Bid, Action
from tradingplatformpoc.trade import Trade, Market
from typing import List


def calculate_costs(bids: List[Bid], trades: List[Trade], clearing_price: float, external_wholesale_price: float):
    """
    All bids and trades should be for the same trading period
    """
    accepted_bids = [x for x in bids if was_bid_accepted(x, clearing_price)]
    agent_ids = set([x.source for x in accepted_bids] + [x.source for x in trades])

    external_bids = [x for x in bids if x.by_external]
    external_trades_on_local_market = [x for x in trades if x.by_external and x.market == Market.LOCAL]
    extra_cost = calculate_extra_cost(external_bids, external_trades_on_local_market, clearing_price,
                                      external_wholesale_price)
    # Now we know how much extra cost that need to be covered. Now we'll figure out how to distribute it.

    error_by_agent = calculate_error_by_agent(accepted_bids, agent_ids, trades)
    cost_to_be_paid_by_agent = distribute_cost(error_by_agent, extra_cost)
    return cost_to_be_paid_by_agent


def calculate_extra_cost(external_bids, external_trades, clearing_price, external_wholesale_price):
    if len(external_bids) != 1:
        raise RuntimeError("Expected 1 and only 1 external grid bid for a single trading period")
    else:
        external_retail_price = external_bids[0].price

    if external_retail_price < clearing_price:
        raise RuntimeError("Unexpected state: External retail price < local clearing price")

    if len(external_trades) == 0:
        return 0
    elif len(external_trades) > 1:
        raise RuntimeError("Unexpected state: More than 1 external grid trade for a single trading period")
    else:
        if external_trades[0].action == Action.BUY:
            external_actual_export = external_trades[0].quantity
            price_difference = clearing_price - external_wholesale_price
            return external_actual_export * price_difference
        else:
            external_actual_import = external_trades[0].quantity
            price_difference = external_retail_price - clearing_price
            return external_actual_import * price_difference


def was_bid_accepted(bid, clearing_price):
    return ((bid.action == Action.SELL) & (bid.price <= clearing_price)) | \
           ((bid.action == Action.BUY) & (bid.price >= clearing_price))


def distribute_cost(error_by_agent, extra_cost):
    """
    Proportional to the absolute error of an agent's prediction, i.e. the difference between bid quantity and actual
    consumption/production.
    """
    if extra_cost == 0.0:
        return {k: 0 for (k, v) in error_by_agent.items()}
    sum_of_abs_errors = sum([abs(v) for (k, v) in error_by_agent.items()])
    perc_of_cost_to_be_paid_by_agent = {k: abs(v) / sum_of_abs_errors for (k, v) in error_by_agent.items()}
    return {k: extra_cost * v for (k, v) in perc_of_cost_to_be_paid_by_agent.items()}


def is_agent_external(accepted_bids_for_agent, trades_for_agent):
    """Helper method to figure out whether an agent represents an external grid, based on bids and trades for the agent.
    """
    if len(trades_for_agent) > 0:
        if trades_for_agent[0].by_external:
            return True
    if len(accepted_bids_for_agent) > 0:
        if accepted_bids_for_agent[0].by_external:
            return True
    return False


def calculate_error_by_agent(accepted_bids, agent_ids, trades):
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


def get_bid_usage(accepted_bids_for_agent, agent_id):
    """Usage is negative if the agent is a supplier of energy"""
    if len(accepted_bids_for_agent) > 1:
        raise RuntimeError("More than 1 bid accepted for agent " + agent_id + " in a single trading period")
    elif len(accepted_bids_for_agent) == 0:
        return 0
    else:
        accepted_bid = accepted_bids_for_agent[0]
        return accepted_bid.quantity if accepted_bid.action == Action.BUY else -accepted_bid.quantity


def get_actual_usage(trades_for_agent, agent_id):
    """Usage is negative if the agent is a supplier of energy"""
    if len(trades_for_agent) > 1:
        raise RuntimeError("More than 1 trade for agent " + agent_id + " in a single trading period")
    elif len(trades_for_agent) == 0:
        return 0
    else:
        trade = trades_for_agent[0]
        return trade.quantity if trade.action == Action.BUY else -trade.quantity
