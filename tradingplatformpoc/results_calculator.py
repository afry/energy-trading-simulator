import datetime
from typing import Collection, Dict, Iterable, List, Tuple

from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.extra_cost import ExtraCost, ExtraCostType
from tradingplatformpoc.trade import Trade


def print_basic_results(agents: Iterable[IAgent], all_trades_dict: Dict[datetime.datetime, Collection[Trade]],
                        all_extra_costs: List[ExtraCost],
                        exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                        exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                        exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                        exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]):
    # FUTURE: Perhaps construct a DF here where each row represents an agent, and there are columns for "quantity
    # heating bought", "sek bought elec for", ... That way we can show it in the UI.
    for agent in agents:
        print_basic_results_for_agent(agent, all_trades_dict, all_extra_costs,
                                      exact_retail_electricity_prices_by_period,
                                      exact_wholesale_electricity_prices_by_period,
                                      exact_retail_heating_prices_by_year_and_month,
                                      exact_wholesale_heating_prices_by_year_and_month)


def print_basic_results_for_agent(agent: IAgent, all_trades_dict: Dict[datetime.datetime, Collection[Trade]],
                                  all_extra_costs: List[ExtraCost],
                                  exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                                  exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                                  exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                  exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]):
    trades_for_agent = [x for v in all_trades_dict.values() for x in v if x.source == agent.guid]

    quantity_bought_elec = sum([x.quantity_pre_loss for x in trades_for_agent
                                if (x.action == Action.BUY) & (x.resource == Resource.ELECTRICITY)])
    quantity_bought_heat = sum([x.quantity_pre_loss for x in trades_for_agent
                                if (x.action == Action.BUY) & (x.resource == Resource.HEATING)])
    quantity_sold_elec = sum([x.quantity_post_loss for x in trades_for_agent
                              if (x.action == Action.SELL) & (x.resource == Resource.ELECTRICITY)])
    quantity_sold_heat = sum([x.quantity_post_loss for x in trades_for_agent
                              if (x.action == Action.SELL) & (x.resource == Resource.HEATING)])
    # For BUY-trades, the buyer pays for the quantity before losses.
    sek_bought_for_elec = sum([x.quantity_pre_loss * x.price for x in trades_for_agent
                               if (x.action == Action.BUY) & (x.resource == Resource.ELECTRICITY)])
    sek_bought_for_heat = sum([x.quantity_pre_loss * x.price for x in trades_for_agent
                               if (x.action == Action.BUY) & (x.resource == Resource.HEATING)])
    # For SELL-trades, the seller gets paid for the quantity after losses.
    # These sums will already have deducted taxes and grid fees, that the seller is to pay
    sek_sold_for_elec = sum([x.quantity_post_loss * x.price for x in trades_for_agent
                             if (x.action == Action.SELL) & (x.resource == Resource.ELECTRICITY)])
    sek_sold_for_heat = sum([x.quantity_post_loss * x.price for x in trades_for_agent
                             if (x.action == Action.SELL) & (x.resource == Resource.HEATING)])
    sek_tax_paid = sum([x.quantity_post_loss * x.tax_paid for x in trades_for_agent])
    sek_grid_fee_paid = sum([x.quantity_post_loss * x.grid_fee_paid for x in trades_for_agent])
    sek_bought_for = sek_bought_for_heat + sek_bought_for_elec
    sek_sold_for = sek_sold_for_heat + sek_sold_for_elec
    sek_traded_for = sek_bought_for + sek_sold_for

    if not isinstance(agent, GridAgent):
        extra_costs_for_bad_bids = sum([ec.cost for ec in all_extra_costs if (ec.agent == agent.guid)
                                        & (ec.cost_type.is_for_bid_inaccuracy())])
        extra_costs_for_heat_cost_discr = sum([ec.cost for ec in all_extra_costs if (ec.agent == agent.guid)
                                               & (ec.cost_type == ExtraCostType.HEAT_EXT_COST_CORR)])
        saved_on_buy, saved_on_sell = get_savings_vs_only_external(trades_for_agent,
                                                                   exact_retail_electricity_prices_by_period,
                                                                   exact_wholesale_electricity_prices_by_period,
                                                                   exact_retail_heating_prices_by_year_and_month,
                                                                   exact_wholesale_heating_prices_by_year_and_month)
        total_saved = saved_on_buy + saved_on_sell - extra_costs_for_heat_cost_discr
        if sek_traded_for > 0:
            print_message("For agent {} saved {:.2f} SEK by using local market, versus only using external grid, "
                          "saving of {:.2f}%".format(agent.guid, total_saved, 100.0 * total_saved / sek_traded_for))

        print_message(
            "For agent {} was penalized with a total of {:.2f} SEK due to inaccurate projections. This brought "
            "total savings to {:.2f} SEK".
            format(agent.guid, extra_costs_for_bad_bids, total_saved - extra_costs_for_bad_bids))

        if isinstance(agent, StorageAgent):
            total_profit_gross = sek_sold_for - sek_bought_for + sek_tax_paid + sek_grid_fee_paid
            total_profit_net = sek_sold_for - sek_bought_for
            print_message("For agent {} total profit was {:.2f} SEK before taxes and grid fees".
                          format(agent.guid, total_profit_gross))
            print_message("For agent {} total tax paid was {:.2f} SEK, and total grid fees paid was {:.2f} SEK".
                          format(agent.guid, sek_tax_paid, sek_grid_fee_paid))
            print_message("For agent {} total profit was {:.2f} SEK after taxes and grid fees".
                          format(agent.guid, total_profit_net))

    # Maybe we want to split this up by energy carrier?
    print_message("For agent {} bought a total of {:.2f} kWh electricity.".format(agent.guid, quantity_bought_elec))
    print_message("For agent {} bought a total of {:.2f} kWh heating.".format(agent.guid, quantity_bought_heat))
    print_message("For agent {} sold a total of {:.2f} kWh electricity.".format(agent.guid, quantity_sold_elec))
    print_message("For agent {} sold a total of {:.2f} kWh heating.".format(agent.guid, quantity_sold_heat))

    if quantity_bought_elec > 0:
        avg_buy_price_elec = sek_bought_for_elec / quantity_bought_elec
        print_message("For agent {} average buy price for electricity was {:.3f} SEK/kWh".
                      format(agent.guid, avg_buy_price_elec))
    if quantity_bought_heat > 0:
        avg_buy_price_heat = sek_bought_for_heat / quantity_bought_heat
        print_message("For agent {} average buy price for heating was {:.3f} SEK/kWh".
                      format(agent.guid, avg_buy_price_heat))
    if quantity_sold_elec > 0:
        avg_sell_price_elec = sek_sold_for_elec / quantity_sold_elec
        print_message("For agent {} average sell price for electricity was {:.3f} SEK/kWh".
                      format(agent.guid, avg_sell_price_elec))
    if quantity_sold_heat > 0:
        avg_sell_price_heat = sek_sold_for_heat / quantity_sold_heat
        print_message("For agent {} average sell price for heating was {:.3f} SEK/kWh".
                      format(agent.guid, avg_sell_price_heat))


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
            # For BUY-trades, the buyer pays for the quantity before losses
            saved_on_buy_vs_using_only_external = saved_on_buy_vs_using_only_external + \
                trade.quantity_pre_loss * (retail_price - trade.price)
        elif trade.action == Action.SELL:
            wholesale_price = get_relevant_price(exact_wholesale_electricity_prices_by_period,
                                                 exact_wholesale_heating_prices_by_year_and_month, period, resource)
            # For SELL-trades, the seller gets paid for the quantity after losses.
            saved_on_sell_vs_using_only_external = saved_on_sell_vs_using_only_external + \
                trade.quantity_post_loss * (trade.price - wholesale_price)
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
