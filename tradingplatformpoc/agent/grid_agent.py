from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.bid import Action, Resource
from tradingplatformpoc.data_store import DataStore
from tradingplatformpoc.trade import Market, Trade


class ElectricityGridAgent(IAgent):
    MAX_TRANSFER_PER_HOUR = 10000  # kW (placeholder value: same limit as FED)

    def __init__(self, data_store: DataStore, guid="ElectricityGridAgent"):
        super().__init__(guid)
        self.data_store = data_store

    def make_bids(self, period):
        # Submit 2 bids here
        # Sell up to MAX_TRANSFER_PER_HOUR kWh at calculate_retail_price(period)
        # Buy up to MAX_TRANSFER_PER_HOUR kWh at calculate_wholesale_price(period)
        retail_price = self.data_store.get_retail_price(period)
        wholesale_price = self.data_store.get_wholesale_price(period)
        bid_to_sell = self.construct_bid(Action.SELL, Resource.ELECTRICITY, self.MAX_TRANSFER_PER_HOUR, retail_price)
        bid_to_buy = self.construct_bid(action=Action.BUY,
                                        resource=Resource.ELECTRICITY,
                                        quantity=self.MAX_TRANSFER_PER_HOUR,
                                        price=wholesale_price)
        bids = [bid_to_sell, bid_to_buy]
        return bids

    def make_prognosis(self, period):
        # FUTURE: Make prognoses of the price, instead of using actual? Although we are already using the day-ahead?
        pass

    def get_actual_usage(self, period):
        pass

    def make_trade_given_clearing_price(self, period, clearing_price):
        # The external grid is used to make up for any differences on the local market. Therefore these will be
        # calculated at a later stage (in calculate_external_trades)
        pass

    def calculate_external_trades(self, trades_excl_external, local_clearing_price):
        trades_to_add = []

        periods = set([trade.period for trade in trades_excl_external])
        for period in periods:
            trades_for_this_period = [trade for trade in trades_excl_external if trade.period == period]
            retail_price = self.data_store.get_retail_price(period)
            wholesale_price = self.data_store.get_wholesale_price(period)

            resource = Resource.ELECTRICITY  # FUTURE: Go through HEATING and maybe COOLING as well
            trades_for_this_resource = [trade for trade in trades_for_this_period if trade.resource == resource]
            self.calculate_external_trades_for_resource_and_market(Market.LOCAL, period, resource, retail_price,
                                                                   trades_for_this_resource, trades_to_add,
                                                                   wholesale_price, local_clearing_price)
            self.calculate_external_trades_for_resource_and_market(Market.EXTERNAL, period, resource, retail_price,
                                                                   trades_for_this_resource, trades_to_add,
                                                                   wholesale_price, local_clearing_price)
        return trades_to_add

    def calculate_external_trades_for_resource_and_market(self, market, period, resource, retail_price,
                                                          trades_for_this_resource, trades_to_add, wholesale_price,
                                                          local_clearing_price):
        trades_for_this_resource_and_market = [trade for trade in trades_for_this_resource if trade.market == market]
        sum_buys = sum([trade.quantity for trade in trades_for_this_resource_and_market if trade.action == Action.BUY])
        sum_sells = sum(
            [trade.quantity for trade in trades_for_this_resource_and_market if trade.action == Action.SELL])
        if sum_buys > sum_sells:
            trades_to_add.append(
                Trade(Action.SELL, resource, sum_buys - sum_sells, retail_price, self.guid, market, period))
            if market == Market.LOCAL:
                if local_clearing_price < retail_price:
                    # This isn't necessarily a problem, per se, but when we move away from perfect predictions,
                    # we'll have to do something when this happens: Basically the market solver believed that locally
                    # produced energy would cover the needs of all agents, but it turned out to not be the case,
                    # so we had to import some energy from the external grid, at a higher price than the local price.
                    # The agents will have to split the extra cost between themselves, in some way. Both producers and
                    # consumers could be to blame - producers may have produced less than they thought they would, and
                    # consumers may have consumed more than they thought they would. We'll have to work out some
                    # proportional way of distributing the extra cost.
                    print("External grid sells at {} SEK/kWh to the local market, but the clearing price was {} "
                          "SEK/kWh.".format(retail_price, local_clearing_price))
                elif local_clearing_price > retail_price:
                    raise RuntimeError("Unexpected result: Local clearing price higher than external retail price")
        elif sum_buys < sum_sells:
            trades_to_add.append(
                Trade(Action.BUY, resource, sum_sells - sum_buys, wholesale_price, self.guid, market, period))
            if market == Market.LOCAL:
                if local_clearing_price > wholesale_price:
                    # This isn't necessarily a problem, per se, but when we move away from perfect predictions,
                    # we'll have to do something when this happens: Basically the market solver believed that there
                    # would be a local deficit, but it turned out to not be the case, instead there was a local
                    # surplus. So, producing agents had to export some energy to the external grid, at a lower price
                    # than the local price. The agents will have to split the extra cost (or rather, missing revenue)
                    # between themselves, in some way. Both producers and consumers could be to blame - producers may
                    # have produced more than they thought they would, and consumers may have consumed less than they
                    # thought they would. We'll have to work out some proportional way of distributing the extra cost.
                    print("External grid buys at {} SEK/kWh from the local market, but the clearing price was {} "
                          "SEK/kWh". format(wholesale_price, local_clearing_price))
                elif local_clearing_price < wholesale_price:
                    raise RuntimeError("Unexpected result: Local clearing price lower than external wholesale price")