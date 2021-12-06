from tradingplatformpoc.bid import Bid, Action
from tradingplatformpoc.trade import Trade
from typing import List


def calculate_extra_cost(external_bids, external_trades, clearing_price):
    if len(external_bids) != 1:
        raise RuntimeError("Expected 1 and only 1 external grid bid for a single trading period")
    else:
        external_retail_price = external_bids[0].price

    if external_retail_price < clearing_price:
        raise RuntimeError("Unexpected state: External retail price < local clearing price")
    elif external_retail_price == clearing_price:
        return 0  # No extra costs in this scenario
    # So here we know that external_retail_price > clearing_price, and we didn't expect to have to import anything

    if len(external_trades) == 0:
        external_actual_import = 0
    elif len(external_trades) > 1:
        raise RuntimeError("Unexpected state: More than 1 external grid trade for a single trading period")
    else:
        if external_trades[0].action == Action.BUY:
            external_actual_import = 0
        else:
            external_actual_import = external_trades[0].quantity

    extra_price = external_retail_price - clearing_price
    return external_actual_import * extra_price


def was_bid_accepted(bid, clearing_price):
    return ((bid.action == Action.SELL) & (bid.price <= clearing_price)) | \
           ((bid.action == Action.BUY) & (bid.price >= clearing_price))


def calculate_costs(bids: List[Bid], trades: List[Trade], clearing_price: float):
    """
    All bids and trades should be for the same trading period
    """
    accepted_bids = [x for x in bids if was_bid_accepted(x, clearing_price)]
    agent_ids = set([x.source for x in accepted_bids] + [x.source for x in trades])

    external_bids = [x for x in bids if x.by_external]
    external_trades = [x for x in trades if x.by_external]
    extra_cost = calculate_extra_cost(external_bids, external_trades, clearing_price)

    error_by_agent = calculate_error_by_agent(accepted_bids, agent_ids, trades)
    cost_to_be_paid_by_agent = calculate_cost(error_by_agent, extra_cost)
    print(cost_to_be_paid_by_agent)


def calculate_cost(error_by_agent, extra_cost):
    sum_of_abs_errors = sum([abs(v) for (k, v) in error_by_agent.items()])
    perc_of_cost_to_be_paid_by_agent = {k: abs(v) / sum_of_abs_errors for (k, v) in error_by_agent.items()}
    return {k: extra_cost * v for (k, v) in perc_of_cost_to_be_paid_by_agent.items()}


def is_agent_external(accepted_bids_for_agent, trades_for_agent):
    if len(trades_for_agent) > 0:
        if trades_for_agent[0].by_external:
            return True
    if len(accepted_bids_for_agent) > 0:
        if accepted_bids_for_agent[0].by_external:
            return True
    return False


def calculate_error_by_agent(accepted_bids, agent_ids, trades):
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
    if len(accepted_bids_for_agent) > 1:
        raise RuntimeError("More than 1 bid accepted for agent " + agent_id + " in a single trading period")
    elif len(accepted_bids_for_agent) == 0:
        return 0
    else:
        accepted_bid = accepted_bids_for_agent[0]
        return accepted_bid.quantity if accepted_bid.action == Action.BUY else -accepted_bid.quantity


def get_actual_usage(trades_for_agent, agent_id):
    if len(trades_for_agent) > 1:
        raise RuntimeError("More than 1 trade for agent " + agent_id + " in a single trading period")
    elif len(trades_for_agent) == 0:
        return 0
    else:
        trade = trades_for_agent[0]
        return trade.quantity if trade.action == Action.BUY else -trade.quantity
