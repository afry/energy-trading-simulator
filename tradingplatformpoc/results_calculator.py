from typing import Iterable

import streamlit as st

from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.bid import Action
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.trade import Trade


def print_basic_results(agents: Iterable[IAgent], all_trades: Iterable[Trade], all_extra_costs_dict: dict,
                        data_store_entity: DataStore):
    st.write(""" ## Results: """)
    for agent in agents:
        print_basic_results_for_agent(agent, all_trades, all_extra_costs_dict, data_store_entity)


def print_basic_results_for_agent(agent: IAgent, all_trades: Iterable[Trade], all_extra_costs_dict: dict,
                                  data_store_entity: DataStore):
    trades_for_agent = [x for x in all_trades if x.source == agent.guid]
    all_extra_costs = list(all_extra_costs_dict.values())

    quantity_bought = sum([x.quantity for x in trades_for_agent if x.action == Action.BUY])
    quantity_sold = sum([x.quantity for x in trades_for_agent if x.action == Action.SELL])
    sek_bought_for = sum([x.quantity * x.price for x in trades_for_agent if x.action == Action.BUY])
    sek_sold_for = sum([x.quantity * x.price for x in trades_for_agent if x.action == Action.SELL])

    if not isinstance(agent, GridAgent):
        extra_costs_for_agent = sum([d[agent.guid] for d in all_extra_costs if (agent.guid in d.keys())])
        saved_on_buy, saved_on_sell = get_savings_vs_only_external(
            data_store_entity, trades_for_agent)
        if sek_bought_for > 0:
            print_message("For agent {} saved {:.2f} SEK when buying electricity by using local market, versus buying "
                          "everything from external grid, saving of {:.2f}%".
                          format(agent.guid, saved_on_buy, 100.0 * saved_on_buy / sek_bought_for))
        if sek_sold_for > 0:
            print_message(
                "For agent {} saved {:.2f} SEK when selling electricity by using local market, versus selling "
                "everything to external grid, saving of {:.2f}%".
                format(agent.guid, saved_on_sell, 100.0 * saved_on_sell / sek_sold_for))

        print_message(
            "For agent {} was penalized with a total of {:.2f} SEK due to inaccurate projections. This brought "
            "total savings to {:.2f} SEK".
            format(agent.guid, extra_costs_for_agent, saved_on_buy + saved_on_sell - extra_costs_for_agent))

        if isinstance(agent, StorageAgent):
            total_profit = sek_sold_for - sek_bought_for
            print_message("For agent {} total profit was {:.2f} SEK".format(agent.guid, total_profit))

    print_message("For agent {} quantity bought was {:.2f} kWh".format(agent.guid, quantity_bought))
    print_message("For agent {} quantity sold was {:.2f} kWh".format(agent.guid, quantity_sold))

    if quantity_bought > 0:
        avg_buy_price = sek_bought_for / quantity_bought
        print_message("For agent {} average buy price was {:.3f} SEK/kWh".format(agent.guid, avg_buy_price))
    if quantity_sold > 0:
        avg_sell_price = sek_sold_for / quantity_sold
        print_message("For agent {} average sell price was {:.3f} SEK/kWh".format(agent.guid, avg_sell_price))


def get_savings_vs_only_external(data_store_entity: DataStore, trades_for_agent: Iterable[Trade]):
    saved_on_buy_vs_using_only_external = 0
    saved_on_sell_vs_using_only_external = 0
    for trade in trades_for_agent:
        period = trade.period
        resource = trade.resource
        external_retail_price = data_store_entity.get_retail_price(period, resource)
        external_wholesale_price = data_store_entity.get_wholesale_price(period, resource)
        if trade.action == Action.BUY:
            saved_on_buy_vs_using_only_external = saved_on_buy_vs_using_only_external + \
                trade.quantity * (external_retail_price - trade.price)
        elif trade.action == Action.SELL:
            saved_on_sell_vs_using_only_external = saved_on_sell_vs_using_only_external + \
                trade.quantity * (trade.price - external_wholesale_price)
    return saved_on_buy_vs_using_only_external, saved_on_sell_vs_using_only_external


def print_message(message: str):
    print(message)
    st.write(message)
