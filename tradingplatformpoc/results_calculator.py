import datetime
from typing import Dict, Iterable, List, Tuple

import streamlit as st

from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.data.extra_cost import ExtraCost
from tradingplatformpoc.trade import Trade


def print_basic_results(agents: Iterable[IAgent], all_trades: Iterable[Trade], all_extra_costs: List[ExtraCost],
                        exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                        exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                        exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                        exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]):
    st.write(""" ## Results: """)
    for agent in agents:
        print_basic_results_for_agent(agent, all_trades, all_extra_costs,
                                      exact_retail_electricity_prices_by_period,
                                      exact_wholesale_electricity_prices_by_period,
                                      exact_retail_heating_prices_by_year_and_month,
                                      exact_wholesale_heating_prices_by_year_and_month)


def print_basic_results_for_agent(agent: IAgent, all_trades: Iterable[Trade], all_extra_costs: List[ExtraCost],
                                  exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                                  exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                                  exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                  exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]):
    trades_for_agent = [x for x in all_trades if x.source == agent.guid]

    quantity_bought = sum([x.quantity for x in trades_for_agent if x.action == Action.BUY])
    quantity_sold = sum([x.quantity for x in trades_for_agent if x.action == Action.SELL])
    sek_bought_for = sum([x.quantity * x.price for x in trades_for_agent if x.action == Action.BUY])
    sek_sold_for = sum([x.quantity * x.price for x in trades_for_agent if x.action == Action.SELL])

    if not isinstance(agent, GridAgent):
        extra_costs_for_agent = sum([ec.cost for ec in all_extra_costs if (ec.agent == agent.guid)])
        saved_on_buy, saved_on_sell = get_savings_vs_only_external(trades_for_agent,
                                                                   exact_retail_electricity_prices_by_period,
                                                                   exact_wholesale_electricity_prices_by_period,
                                                                   exact_retail_heating_prices_by_year_and_month,
                                                                   exact_wholesale_heating_prices_by_year_and_month)
        if sek_bought_for > 0:
            print_message("For agent {} saved {:.2f} SEK when buying energy by using local market, versus buying "
                          "everything from external grid, saving of {:.2f}%".
                          format(agent.guid, saved_on_buy, 100.0 * saved_on_buy / sek_bought_for))
        if sek_sold_for > 0:
            print_message(
                "For agent {} saved {:.2f} SEK when selling energy by using local market, versus selling "
                "everything to external grid, saving of {:.2f}%".
                format(agent.guid, saved_on_sell, 100.0 * saved_on_sell / sek_sold_for))

        print_message(
            "For agent {} was penalized with a total of {:.2f} SEK due to inaccurate projections. This brought "
            "total savings to {:.2f} SEK".
            format(agent.guid, extra_costs_for_agent, saved_on_buy + saved_on_sell - extra_costs_for_agent))

        if isinstance(agent, StorageAgent):
            total_profit = sek_sold_for - sek_bought_for
            print_message("For agent {} total profit was {:.2f} SEK".format(agent.guid, total_profit))

    # Maybe we want to split this up by energy carrier?
    print_message("For agent {} quantity bought was {:.2f} kWh".format(agent.guid, quantity_bought))
    print_message("For agent {} quantity sold was {:.2f} kWh".format(agent.guid, quantity_sold))

    if quantity_bought > 0:
        avg_buy_price = sek_bought_for / quantity_bought
        print_message("For agent {} average buy price was {:.3f} SEK/kWh".format(agent.guid, avg_buy_price))
    if quantity_sold > 0:
        avg_sell_price = sek_sold_for / quantity_sold
        print_message("For agent {} average sell price was {:.3f} SEK/kWh".format(agent.guid, avg_sell_price))


def get_savings_vs_only_external(trades_for_agent: Iterable[Trade],
                                 exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                 exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]):
    saved_on_buy_vs_using_only_external = 0
    saved_on_sell_vs_using_only_external = 0
    for trade in trades_for_agent:
        period = trade.period
        resource = trade.resource
        if trade.action == Action.BUY:
            retail_price = get_relevant_price(exact_retail_electricity_prices_by_period,
                                              exact_retail_heating_prices_by_year_and_month, period, resource)
            saved_on_buy_vs_using_only_external = saved_on_buy_vs_using_only_external + \
                trade.quantity * (retail_price - trade.price)
        elif trade.action == Action.SELL:
            wholesale_price = get_relevant_price(exact_wholesale_electricity_prices_by_period,
                                                 exact_wholesale_heating_prices_by_year_and_month, period, resource)
            saved_on_sell_vs_using_only_external = saved_on_sell_vs_using_only_external + \
                trade.quantity * (trade.price - wholesale_price)
    return saved_on_buy_vs_using_only_external, saved_on_sell_vs_using_only_external


def get_relevant_price(electricity_prices_by_period: Dict[datetime.datetime, float],
                       heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                       period: datetime.datetime, resource: Resource):
    if resource == Resource.ELECTRICITY:
        return electricity_prices_by_period[period]
    elif resource == Resource.HEATING:
        return heating_prices_by_year_and_month[(period.year, period.month)]
    else:
        raise RuntimeError("Method not implemented for resource " + resource.name)


def print_message(message: str):
    print(message)
    st.write(message)
