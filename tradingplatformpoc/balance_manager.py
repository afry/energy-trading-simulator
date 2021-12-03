from tradingplatformpoc.bid import Bid, Action
from tradingplatformpoc.trade import Trade
from typing import List


def calculate_costs(bids: List[Bid], trades: List[Trade], clearing_price: float):
    """
    All bids and trades should be for the same trading period
    """
    accepted_bids = [x for x in bids if ((x.action == Action.SELL) & (x.price <= clearing_price)) |
                     ((x.action == Action.BUY) & (x.price >= clearing_price))]
    agent_ids = set([x.source for x in accepted_bids] + [x.source for x in trades])
    error_by_agent = calculate_error_by_agent(accepted_bids, agent_ids, trades)
    print(error_by_agent)


def calculate_error_by_agent(accepted_bids, agent_ids, trades):
    error_by_agent = {}
    for agent_id in agent_ids:
        accepted_bids_for_agent = [x for x in accepted_bids if x.source == agent_id]
        trades_for_agent = [x for x in trades if x.source == agent_id]
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
