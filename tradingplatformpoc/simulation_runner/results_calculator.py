import pandas as pd

from tradingplatformpoc.market.bid import Action


class AggregatedTrades:

    def __init__(self, external_trades_df: pd.DataFrame, value_column_name: str = 'quantity_post_loss'):
        """
        Expected columns in external_trades_df:
        ['period', 'action', 'price', value_column_name]
        """
        # Sold by the external = bought by the LEC
        # So a positive "net" means the LEC imported
        external_trades_df['net_imported'] = external_trades_df.apply(lambda x: x[value_column_name]
                                                                      if x.action == Action.SELL
                                                                      else -x[value_column_name],
                                                                      axis=1)
        self.sum_net_import = external_trades_df['net_imported'].sum()
        self.monthly_sum_net_import = external_trades_df['net_imported']. \
            groupby(external_trades_df['period'].dt.month).sum()
        self.monthly_max_net_import = external_trades_df['net_imported']. \
            groupby(external_trades_df['period'].dt.month).max()
        self.sum_lec_expenditure = (external_trades_df['net_imported'] * external_trades_df['price']).sum()
