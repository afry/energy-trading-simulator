import datetime
from typing import Dict, Tuple, Iterable

import pandas as pd

from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.agent.storage_agent import StorageAgent
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.extra_cost import ExtraCostType
from tradingplatformpoc.results.results_key import ResultsKey


def calc_basic_results(agents: Iterable[IAgent], all_trades_df: pd.DataFrame, extra_costs_df: pd.DataFrame,
                       exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                       exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                       exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                       exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]) -> \
        Dict[str, Dict[ResultsKey, float]]:
    results_by_agent = {}
    for agent in agents:
        results_by_agent[agent.guid] = calc_basic_results_for_agent(agent, all_trades_df, extra_costs_df,
                                                                    exact_retail_electricity_prices_by_period,
                                                                    exact_wholesale_electricity_prices_by_period,
                                                                    exact_retail_heating_prices_by_year_and_month,
                                                                    exact_wholesale_heating_prices_by_year_and_month)
    return results_by_agent


def calc_basic_results_for_agent(agent: IAgent, all_trades: pd.DataFrame, all_extra_costs: pd.DataFrame,
                                 exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                 exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]) -> \
        Dict[ResultsKey, float]:
    results_dict = {}
    trades_df = all_trades.loc[all_trades.source == agent.guid]

    elec_buy_trades = trades_df.loc[(trades_df.action == Action.BUY) & (trades_df.resource == Resource.ELECTRICITY)]
    heat_buy_trades = trades_df.loc[(trades_df.action == Action.BUY) & (trades_df.resource == Resource.HEATING)]
    elec_sell_trades = trades_df.loc[(trades_df.action == Action.SELL) & (trades_df.resource == Resource.ELECTRICITY)]
    heat_sell_trades = trades_df.loc[(trades_df.action == Action.SELL) & (trades_df.resource == Resource.HEATING)]

    quantity_bought_elec = elec_buy_trades.quantity_pre_loss.sum()
    quantity_bought_heat = heat_buy_trades.quantity_pre_loss.sum()
    quantity_sold_elec = elec_sell_trades.quantity_post_loss.sum()
    quantity_sold_heat = heat_sell_trades.quantity_post_loss.sum()
    # For BUY-trades, the buyer pays for the quantity before losses.
    sek_bought_for_elec = elec_buy_trades.apply(lambda x: x.quantity_pre_loss * x.price, axis=1).sum() if \
        len(elec_buy_trades) > 0 else 0.0  # pandas can log a FutureWarning if trying to sum on an apply of an empty df
    sek_bought_for_heat = heat_buy_trades.apply(lambda x: x.quantity_pre_loss * x.price, axis=1).sum() if \
        len(heat_buy_trades) > 0 else 0.0
    # For SELL-trades, the seller gets paid for the quantity after losses.
    # These sums will already have deducted taxes and grid fees, that the seller is to pay
    sek_sold_for_elec = elec_sell_trades.apply(lambda x: x.quantity_post_loss * x.price, axis=1).sum() if \
        len(elec_sell_trades) > 0 else 0.0
    sek_sold_for_heat = heat_sell_trades.apply(lambda x: x.quantity_post_loss * x.price, axis=1).sum() if \
        len(heat_sell_trades) > 0 else 0.0
    sek_tax_paid = trades_df.apply(lambda x: x.quantity_post_loss * x.tax_paid, axis=1).sum()
    sek_grid_fee_paid = trades_df.apply(lambda x: x.quantity_post_loss * x.grid_fee_paid, axis=1).sum()
    sek_bought_for = sek_bought_for_heat + sek_bought_for_elec
    sek_sold_for = sek_sold_for_heat + sek_sold_for_elec
    sek_traded_for = sek_bought_for + sek_sold_for

    if not isinstance(agent, GridAgent):
        ec_df = all_extra_costs.loc[all_extra_costs.agent == agent.guid]
        extra_costs_for_bad_bids = ec_df.loc[ec_df.cost_type.apply(lambda x: x.is_for_bid_inaccuracy())].cost.sum()
        extra_costs_for_heat_cost_discr = ec_df.loc[ec_df.cost_type == ExtraCostType.HEAT_EXT_COST_CORR].cost.sum()

        saved_on_buy, saved_on_sell = get_savings_vs_only_external(trades_df,
                                                                   exact_retail_electricity_prices_by_period,
                                                                   exact_wholesale_electricity_prices_by_period,
                                                                   exact_retail_heating_prices_by_year_and_month,
                                                                   exact_wholesale_heating_prices_by_year_and_month)
        total_saved = saved_on_buy + saved_on_sell - extra_costs_for_heat_cost_discr
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

    print_message("For agent {} bought a total of {:.2f} kWh electricity.".format(agent.guid, quantity_bought_elec))
    print_message("For agent {} bought a total of {:.2f} kWh heating.".format(agent.guid, quantity_bought_heat))
    print_message("For agent {} sold a total of {:.2f} kWh electricity.".format(agent.guid, quantity_sold_elec))
    print_message("For agent {} sold a total of {:.2f} kWh heating.".format(agent.guid, quantity_sold_heat))
    results_dict[ResultsKey.ELEC_BOUGHT] = quantity_bought_elec
    results_dict[ResultsKey.HEAT_BOUGHT] = quantity_bought_heat
    results_dict[ResultsKey.ELEC_SOLD] = quantity_sold_elec
    results_dict[ResultsKey.HEAT_SOLD] = quantity_sold_heat

    if quantity_bought_elec > 0:
        avg_buy_price_elec = sek_bought_for_elec / quantity_bought_elec
        print_message("For agent {} average buy price for electricity was {:.3f} SEK/kWh".
                      format(agent.guid, avg_buy_price_elec))
        results_dict[ResultsKey.AVG_BUY_PRICE_ELEC] = avg_buy_price_elec
    if quantity_bought_heat > 0:
        avg_buy_price_heat = sek_bought_for_heat / quantity_bought_heat
        print_message("For agent {} average buy price for heating was {:.3f} SEK/kWh".
                      format(agent.guid, avg_buy_price_heat))
        results_dict[ResultsKey.AVG_BUY_PRICE_HEAT] = avg_buy_price_heat
    if quantity_sold_elec > 0:
        avg_sell_price_elec = sek_sold_for_elec / quantity_sold_elec
        print_message("For agent {} average sell price for electricity was {:.3f} SEK/kWh".
                      format(agent.guid, avg_sell_price_elec))
        results_dict[ResultsKey.AVG_SELL_PRICE_ELEC] = avg_sell_price_elec
    if quantity_sold_heat > 0:
        avg_sell_price_heat = sek_sold_for_heat / quantity_sold_heat
        print_message("For agent {} average sell price for heating was {:.3f} SEK/kWh".
                      format(agent.guid, avg_sell_price_heat))
        results_dict[ResultsKey.AVG_SELL_PRICE_HEAT] = avg_sell_price_heat
    return results_dict


def get_savings_vs_only_external(trades_for_agent: pd.DataFrame,
                                 exact_retail_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_wholesale_electricity_prices_by_period: Dict[datetime.datetime, float],
                                 exact_retail_heating_prices_by_year_and_month: Dict[Tuple[int, int], float],
                                 exact_wholesale_heating_prices_by_year_and_month: Dict[Tuple[int, int], float]) -> \
        Tuple[float, float]:
    saved_on_buy_vs_using_only_external = 0
    saved_on_sell_vs_using_only_external = 0
    for _i, trade in trades_for_agent.iterrows():
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
