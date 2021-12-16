
from tradingplatformpoc import data_store
from tradingplatformpoc.bid import Action
from tradingplatformpoc.agent.grid_agent import ElectricityGridAgent


def print_basic_results(agents, all_trades_list, all_extra_costs_dict, data_store_entity: data_store):
    for agent in agents:
        print_basic_results_for_agent(agent, all_trades_list, all_extra_costs_dict, data_store_entity)


def print_basic_results_for_agent(agent, all_trades_list, all_extra_costs_dict, data_store_entity: data_store):
    trades_for_agent = [x for x in all_trades_list if x.source == agent.guid]
    all_extra_costs = list(all_extra_costs_dict.values())

    if not isinstance(agent, ElectricityGridAgent):
        extra_costs_for_agent = sum([d[agent.guid] for d in all_extra_costs if (agent.guid in d.keys())])
        saved_vs_using_only_external = get_savings_vs_only_external(data_store_entity, trades_for_agent)
        savings_minus_penalties = saved_vs_using_only_external - extra_costs_for_agent
        print("For agent {} saved {:.2f} SEK by using local market, versus buying everything from external grid.".
              format(agent.guid, savings_minus_penalties))

        print("For agent {} was penalized with a total of {:.2f} SEK due to inaccurate projections".
              format(agent.guid, extra_costs_for_agent))

    quantity_bought = sum([x.quantity for x in trades_for_agent if x.action == Action.BUY])
    quantity_sold = sum([x.quantity for x in trades_for_agent if x.action == Action.SELL])
    sek_bought_for = sum([x.quantity * x.price for x in trades_for_agent if x.action == Action.BUY])
    sek_sold_for = sum([x.quantity * x.price for x in trades_for_agent if x.action == Action.SELL])

    print("For agent {} quantity bought was {:.3f} kWh".format(agent.guid, quantity_bought))
    print("For agent {} quantity sold was {:.3f} kWh".format(agent.guid, quantity_sold))

    if quantity_bought > 0:
        avg_buy_price = sek_bought_for / quantity_bought
        print("For agent {} average buy price was {:.3f} SEK/kWh".format(agent.guid, avg_buy_price))
    if quantity_sold > 0:
        avg_sell_price = sek_sold_for / quantity_sold
        print("For agent {} average sell price was {:.3f} SEK/kWh".format(agent.guid, avg_sell_price))


def get_savings_vs_only_external(data_store_entity, trades_for_agent):
    saved_vs_using_only_external = 0
    for trade in trades_for_agent:
        period = trade.period
        external_retail_price = data_store_entity.get_retail_price(period)
        external_wholesale_price = data_store_entity.get_wholesale_price(period)
        if trade.action == Action.BUY:
            saved_vs_using_only_external = saved_vs_using_only_external + \
                                           trade.quantity * (external_retail_price - trade.price)
        elif trade.action == Action.SELL:
            saved_vs_using_only_external = saved_vs_using_only_external + \
                                           trade.quantity * (trade.price - external_wholesale_price)
    return saved_vs_using_only_external
