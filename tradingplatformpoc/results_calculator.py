from typing import Iterable

from tradingplatformpoc.agent.grid_agent import ElectricityGridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.bid import Action
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.trade import Trade

import streamlit as st


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

    if not isinstance(agent, ElectricityGridAgent):
        extra_costs_for_agent = sum([d[agent.guid] for d in all_extra_costs if (agent.guid in d.keys())])
        saved_on_buy, saved_on_sell = get_savings_vs_only_external(
            data_store_entity, trades_for_agent)
        if sek_bought_for > 0:
            print("For agent {} saved {:.2f} SEK when buying electricity by using local market, versus buying "
                  "everything from external grid, saving of {:.2f}%".
                  format(agent.guid, saved_on_buy, 100.0 * saved_on_buy / sek_bought_for))
            st.write("For agent {} saved {:.2f} SEK when buying electricity by using local market, versus buying "
                  "everything from external grid, saving of {:.2f}%".
                  format(agent.guid, saved_on_buy, 100.0 * saved_on_buy / sek_bought_for))
        if sek_sold_for > 0:
            print("For agent {} saved {:.2f} SEK when selling electricity by using local market, versus selling "
                  "everything to external grid, saving of {:.2f}%".
                  format(agent.guid, saved_on_sell, 100.0 * saved_on_sell / sek_sold_for))
            st.write("For agent {} saved {:.2f} SEK when selling electricity by using local market, versus selling "
                  "everything to external grid, saving of {:.2f}%".
                  format(agent.guid, saved_on_sell, 100.0 * saved_on_sell / sek_sold_for))

        print("For agent {} was penalized with a total of {:.2f} SEK due to inaccurate projections. This brought "
              "total savings to {:.2f} SEK".
              format(agent.guid, extra_costs_for_agent, saved_on_buy + saved_on_sell - extra_costs_for_agent))
        st.write("For agent {} was penalized with a total of {:.2f} SEK due to inaccurate projections. This brought "
              "total savings to {:.2f} SEK".
              format(agent.guid, extra_costs_for_agent, saved_on_buy + saved_on_sell - extra_costs_for_agent))

        if isinstance(agent, StorageAgent):
            total_profit = sek_sold_for - sek_bought_for
            print("For agent {} total profit was {:.2f} SEK".format(agent.guid, total_profit))
            st.write("For agent {} total profit was {:.2f} SEK".format(agent.guid, total_profit))

    print("For agent {} quantity bought was {:.2f} kWh".format(agent.guid, quantity_bought))
    print("For agent {} quantity sold was {:.2f} kWh".format(agent.guid, quantity_sold))
    st.write("For agent {} quantity bought was {:.2f} kWh".format(agent.guid, quantity_bought))
    st.write("For agent {} quantity sold was {:.2f} kWh".format(agent.guid, quantity_sold))

    if quantity_bought > 0:
        avg_buy_price = sek_bought_for / quantity_bought
        print("For agent {} average buy price was {:.3f} SEK/kWh".format(agent.guid, avg_buy_price))
        st.write("For agent {} average buy price was {:.3f} SEK/kWh".format(agent.guid, avg_buy_price))
    if quantity_sold > 0:
        avg_sell_price = sek_sold_for / quantity_sold
        print("For agent {} average sell price was {:.3f} SEK/kWh".format(agent.guid, avg_sell_price))
        st.write("For agent {} average sell price was {:.3f} SEK/kWh".format(agent.guid, avg_sell_price))


def get_savings_vs_only_external(data_store_entity: DataStore, trades_for_agent: Iterable[Trade]):
    saved_on_buy_vs_using_only_external = 0
    saved_on_sell_vs_using_only_external = 0
    for trade in trades_for_agent:
        period = trade.period
        external_retail_price = data_store_entity.get_retail_price(period)
        external_wholesale_price = data_store_entity.get_wholesale_price(period)
        if trade.action == Action.BUY:
            saved_on_buy_vs_using_only_external = saved_on_buy_vs_using_only_external + \
                trade.quantity * (external_retail_price - trade.price)
        elif trade.action == Action.SELL:
            saved_on_sell_vs_using_only_external = saved_on_sell_vs_using_only_external + \
                trade.quantity * (trade.price - external_wholesale_price)
    return saved_on_buy_vs_using_only_external, saved_on_sell_vs_using_only_external
