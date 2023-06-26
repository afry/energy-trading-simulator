import datetime
from typing import Dict, Iterable, Tuple

from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.results.results_key import ResultsKey
from tradingplatformpoc.sql.extra_cost.crud import db_to_aggregated_extra_costs_by_agent
from tradingplatformpoc.sql.trade.crud import db_to_aggregated_trades_by_agent, db_to_trades_by_agent


def calc_basic_results(agents: Iterable[IAgent], job_id: str,
                       exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                       exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                       exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                       exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]) -> \
        Dict[str, Dict[ResultsKey, float]]:
    results_by_agent = {}
    for agent in agents:
        results_by_agent[agent.guid] = calc_basic_results_for_agent(agent, job_id,
                                                                    exact_retail_electricity_prices_by_period,
                                                                    exact_wholesale_electricity_prices_by_period,
                                                                    exact_retail_heating_prices_by_year_and_month,
                                                                    exact_wholesale_heating_prices_by_year_and_month)
    return results_by_agent


def calc_basic_results_for_agent(agent: IAgent, job_id: str,
                                 exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                 exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]) -> \
        Dict[ResultsKey, float]:
    """
    For the given agent, does various aggregations of trades and extra costs, and returns results in a dict. The
    possible keys in the dict are defined in the Enum ResultsKey.
    """
    results_dict: Dict[ResultsKey, float] = {}
    sek_tax_paid = 0.0
    sek_grid_fee_paid = 0.0
    sek_price = {'sek_bougt_for_elec': 0.0, 'sek_sold_for_elec': 0.0,
                 'sek_bougt_for_heat': 0.0, 'sek_sold_for_heat': 0.0}
    res = db_to_aggregated_trades_by_agent(agent.guid, job_id)
    for elem in res:
        if (elem.resource == Resource.ELECTRICITY) & (elem.action == Action.BUY):
            results_dict, sek_price['sek_bougt_for_elec'], sek_tax_paid, sek_grid_fee_paid = \
                extract_aggregated_trades(elem, results_dict, agent.guid,
                                          ResultsKey.ELEC_BOUGHT, ResultsKey.AVG_BUY_PRICE_ELEC,
                                          sek_tax_paid, sek_grid_fee_paid,
                                          Resource.ELECTRICITY, Action.BUY)
        elif (elem.resource == Resource.ELECTRICITY) & (elem.action == Action.SELL):
            results_dict, sek_price['sek_sold_for_elec'], sek_tax_paid, sek_grid_fee_paid = \
                extract_aggregated_trades(elem, results_dict, agent.guid,
                                          ResultsKey.ELEC_SOLD, ResultsKey.AVG_SELL_PRICE_ELEC,
                                          sek_tax_paid, sek_grid_fee_paid,
                                          Resource.ELECTRICITY, Action.SELL)
        elif (elem.resource == Resource.HEATING) & (elem.action == Action.BUY):
            results_dict, sek_price['sek_bougt_for_heat'], sek_tax_paid, sek_grid_fee_paid = \
                extract_aggregated_trades(elem, results_dict, agent.guid,
                                          ResultsKey.HEAT_BOUGHT, ResultsKey.AVG_BUY_PRICE_HEAT,
                                          sek_tax_paid, sek_grid_fee_paid,
                                          Resource.HEATING, Action.BUY)
        elif (elem.resource == Resource.HEATING) & (elem.action == Action.SELL):
            results_dict, sek_price['sek_sold_for_heat'], sek_tax_paid, sek_grid_fee_paid = \
                extract_aggregated_trades(elem, results_dict, agent.guid,
                                          ResultsKey.HEAT_SOLD, ResultsKey.AVG_SELL_PRICE_HEAT,
                                          sek_tax_paid, sek_grid_fee_paid,
                                          Resource.HEATING, Action.SELL)

    if not isinstance(agent, GridAgent):
        extra_costs_for_bad_bids, extra_costs_for_heat_cost_discr = \
            db_to_aggregated_extra_costs_by_agent(agent.guid, job_id)

        saved_on_buy, saved_on_sell = get_savings_vs_only_external(agent.guid, job_id,
                                                                   exact_retail_electricity_prices_by_period,
                                                                   exact_wholesale_electricity_prices_by_period,
                                                                   exact_retail_heating_prices_by_year_and_month,
                                                                   exact_wholesale_heating_prices_by_year_and_month)
        total_saved = saved_on_buy + saved_on_sell - extra_costs_for_heat_cost_discr

        sek_bought_for = sek_price['sek_bougt_for_heat'] + sek_price['sek_bougt_for_elec']
        sek_sold_for = sek_price['sek_sold_for_heat'] + sek_price['sek_sold_for_elec']
        sek_traded_for = sek_bought_for + sek_sold_for

        if sek_traded_for > 0:
            results_dict[ResultsKey.SAVING_ABS_GROSS] = total_saved
            results_dict[ResultsKey.SAVING_REL_GROSS] = 100.0 * total_saved / sek_traded_for
            print_message("For agent {} saved {:.2f} SEK by using local market, versus only using external grid, "
                          "saving of {:.2f}%".format(agent.guid, total_saved, 100.0 * total_saved / sek_traded_for))

        print_message(
            "For agent {} was penalized with a total of {:.2f} SEK due to inaccurate projections. This brought "
            "total savings to {:.2f} SEK".
            format(agent.guid, extra_costs_for_bad_bids, total_saved - extra_costs_for_bad_bids))
        results_dict[ResultsKey.SAVING_ABS_NET] = total_saved - extra_costs_for_bad_bids
        results_dict[ResultsKey.SAVING_REL_NET] = 100.0 * (total_saved - extra_costs_for_bad_bids) / sek_traded_for
        results_dict[ResultsKey.PENALTIES_BID_INACCURACY] = extra_costs_for_bad_bids

        if isinstance(agent, StorageAgent):
            total_profit_gross = sek_sold_for - sek_bought_for + sek_tax_paid + sek_grid_fee_paid
            total_profit_net = sek_sold_for - sek_bought_for
            print_message("For agent {} total profit was {:.2f} SEK before taxes and grid fees".
                          format(agent.guid, total_profit_gross))
            print_message("For agent {} total tax paid was {:.2f} SEK, and total grid fees paid was {:.2f} SEK".
                          format(agent.guid, sek_tax_paid, sek_grid_fee_paid))
            print_message("For agent {} total profit was {:.2f} SEK after taxes and grid fees".
                          format(agent.guid, total_profit_net))
            results_dict[ResultsKey.PROFIT_GROSS] = total_profit_gross
            results_dict[ResultsKey.TAX_PAID] = sek_tax_paid
            results_dict[ResultsKey.GRID_FEES_PAID] = sek_grid_fee_paid
            results_dict[ResultsKey.PROFIT_NET] = total_profit_net

    return results_dict


def get_savings_vs_only_external(agent_guid: str, job_id: str,
                                 exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                 exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]) -> \
        Tuple[float, float]:
    saved_on_buy_vs_using_only_external = 0
    saved_on_sell_vs_using_only_external = 0
    trades = db_to_trades_by_agent(agent_guid, job_id)
    for trade in trades:
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


def extract_aggregated_trades(elem, results_dict: dict, agent_guid: str,
                              quantity_key: ResultsKey, avg_key: ResultsKey,
                              sek_tax_paid: float, sek_grid_fee_paid: float,
                              resource: Resource, action: Action) \
        -> Tuple[Dict[ResultsKey, float], float, float, float]:
    if action == Action.BUY:
        results_dict[quantity_key] = elem.sum_quantity_pre_loss
        print_message("For agent {} bought a total of {:.2f} kWh {}.".format(agent_guid, results_dict[quantity_key],
                                                                             resource.name.lower()))
        sek = elem.sum_total_bought_for

    elif action == Action.SELL:
        results_dict[quantity_key] = elem.sum_quantity_post_loss
        print_message("For agent {} sold a total of {:.2f} kWh {}.".format(agent_guid, results_dict[quantity_key],
                                                                           resource.name.lower()))
        sek = elem.sum_total_sold_for
    
    sek_tax_paid += elem.sum_tax_paid_for_quantities
    sek_grid_fee_paid += elem.grid_fee_paid_for_quantity

    if results_dict[quantity_key] > 0:
        avg_price = sek / results_dict[quantity_key]
        print_message("For agent {} average {} price for {:.3f} was {} SEK/kWh".
                      format(agent_guid, action.name.lower(), avg_price, resource.name.lower()))
        results_dict[avg_key] = avg_price
    else:
        results_dict[avg_key] = 0.0

    return results_dict, sek, sek_tax_paid, sek_grid_fee_paid
