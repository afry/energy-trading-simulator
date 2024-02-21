import datetime
import logging
from typing import Any, Dict, List

import pandas as pd

from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.sql.input_data.crud import read_input_column_df_from_db
from tradingplatformpoc.sql.results.crud import save_results
from tradingplatformpoc.sql.results.models import PreCalculatedResults, ResultsKey
from tradingplatformpoc.sql.trade.crud import get_external_trades_df, get_total_grid_fee_paid_on_internal_trades, \
    get_total_tax_paid

logger = logging.getLogger(__name__)


class AggregatedTrades:
    net_energy_spend: float
    sum_import: float
    sum_export: float
    sum_net_import: float
    monthly_sum_import: Dict[int, float]
    monthly_sum_export: Dict[int, float]
    monthly_sum_net_import: Dict[int, float]
    monthly_max_net_import: Dict[int, float]
    sum_import_jan_feb: float
    sum_export_jan_feb: float
    sum_import_below_1_c: float
    sum_export_below_1_c: float

    def __init__(self, external_trades_df: pd.DataFrame, periods_above_1_c: List[datetime.datetime],
                 value_column_name: str = 'quantity_post_loss'):
        """
        Expected columns in external_trades_df:
        ['period', 'action', 'price', value_column_name]

        Sold by the external = bought by the LEC
        So a positive "net" means the LEC imported
        """
        external_sell_trades = external_trades_df[external_trades_df['action'] == Action.SELL]
        external_buy_trades = external_trades_df[external_trades_df['action'] == Action.BUY]

        monthly_sum_import_series = external_sell_trades[value_column_name]. \
            groupby(external_sell_trades['period'].dt.month).sum()
        monthly_sum_export_series = external_buy_trades[value_column_name]. \
            groupby(external_buy_trades['period'].dt.month).sum()

        self.monthly_sum_import = monthly_sum_import_series.to_dict()
        self.monthly_sum_export = monthly_sum_export_series.to_dict()

        self.sum_import = monthly_sum_import_series.sum()
        self.sum_export = monthly_sum_export_series.sum()
        self.sum_net_import = self.sum_import - self.sum_export

        self.sum_import_jan_feb = monthly_sum_import_series.get(1, 0) + monthly_sum_import_series.get(2, 0)
        self.sum_export_jan_feb = monthly_sum_export_series.get(1, 0) + monthly_sum_export_series.get(2, 0)

        self.sum_import_below_1_c = external_sell_trades. \
            loc[external_sell_trades['period'].isin(periods_above_1_c), value_column_name].sum()
        self.sum_export_below_1_c = external_buy_trades. \
            loc[external_buy_trades['period'].isin(periods_above_1_c), value_column_name].sum()
        external_trades_df['net_imported'] = external_trades_df.apply(lambda x: x[value_column_name]
                                                                      if x.action == Action.SELL
                                                                      else -x[value_column_name],
                                                                      axis=1)
        self.net_energy_spend = (external_trades_df['net_imported'] * external_trades_df['price']).sum()
        grouped_by_month = external_trades_df['net_imported'].groupby(external_trades_df['period'].dt.month)
        # These are converted to dicts, to make them JSON-serializable
        self.monthly_sum_net_import = grouped_by_month.sum().to_dict()
        self.monthly_max_net_import = grouped_by_month.max().to_dict()


def calculate_results_and_save(job_id: str, agents: List[IAgent]):
    """
    Pre-calculates some results, so that they can be easily fetched later.
    """
    logger.info('Calculating some results')
    result_dict: Dict[str, Any] = {}
    df = get_external_trades_df([job_id])
    temperature_df = read_input_column_df_from_db('temperature')
    periods_below_1_c = list(temperature_df[temperature_df['temperature'].values < 1.0].period)
    elec_trades = df[(df.resource == Resource.ELECTRICITY)].copy()
    heat_trades = df[(df.resource == Resource.HEATING)].copy()
    agg_elec_trades = AggregatedTrades(elec_trades, periods_below_1_c)
    agg_heat_trades = AggregatedTrades(heat_trades, periods_below_1_c)
    result_dict[ResultsKey.NET_ENERGY_SPEND] = (agg_elec_trades.net_energy_spend
                                                + agg_heat_trades.net_energy_spend)
    result_dict[ResultsKey.SUM_IMPORT_ELEC] = agg_elec_trades.sum_import
    result_dict[ResultsKey.SUM_EXPORT_ELEC] = agg_elec_trades.sum_export
    result_dict[ResultsKey.SUM_NET_IMPORT_ELEC] = agg_elec_trades.sum_net_import
    result_dict[ResultsKey.MONTHLY_SUM_IMPORT_ELEC] = agg_elec_trades.monthly_sum_import
    result_dict[ResultsKey.MONTHLY_SUM_EXPORT_ELEC] = agg_elec_trades.monthly_sum_export
    result_dict[ResultsKey.MONTHLY_SUM_NET_IMPORT_ELEC] = agg_elec_trades.monthly_sum_net_import
    result_dict[ResultsKey.MONTHLY_MAX_NET_IMPORT_ELEC] = agg_elec_trades.monthly_max_net_import
    result_dict[ResultsKey.SUM_IMPORT_HEAT] = agg_heat_trades.sum_import
    result_dict[ResultsKey.SUM_EXPORT_HEAT] = agg_heat_trades.sum_export
    result_dict[ResultsKey.SUM_NET_IMPORT_HEAT] = agg_heat_trades.sum_net_import
    result_dict[ResultsKey.MONTHLY_SUM_IMPORT_HEAT] = agg_heat_trades.monthly_sum_import
    result_dict[ResultsKey.MONTHLY_SUM_EXPORT_HEAT] = agg_heat_trades.monthly_sum_export
    result_dict[ResultsKey.MONTHLY_SUM_NET_IMPORT_HEAT] = agg_heat_trades.monthly_sum_net_import
    result_dict[ResultsKey.MONTHLY_MAX_NET_IMPORT_HEAT] = agg_heat_trades.monthly_max_net_import
    # Aggregated import/export, split on period/temperature
    result_dict[ResultsKey.SUM_IMPORT_JAN_FEB_ELEC] = agg_elec_trades.sum_import_jan_feb
    result_dict[ResultsKey.SUM_EXPORT_JAN_FEB_ELEC] = agg_elec_trades.sum_export_jan_feb
    result_dict[ResultsKey.SUM_IMPORT_BELOW_1_C_ELEC] = agg_elec_trades.sum_import_below_1_c
    result_dict[ResultsKey.SUM_EXPORT_BELOW_1_C_ELEC] = agg_elec_trades.sum_export_below_1_c
    result_dict[ResultsKey.SUM_IMPORT_JAN_FEB_HEAT] = agg_heat_trades.sum_import_jan_feb
    result_dict[ResultsKey.SUM_EXPORT_JAN_FEB_HEAT] = agg_heat_trades.sum_export_jan_feb
    result_dict[ResultsKey.SUM_IMPORT_BELOW_1_C_HEAT] = agg_heat_trades.sum_import_below_1_c
    result_dict[ResultsKey.SUM_EXPORT_BELOW_1_C_HEAT] = agg_heat_trades.sum_export_below_1_c
    # Aggregated local production
    local_prod_dict = aggregated_local_productions(agents, agg_heat_trades.sum_net_import)
    result_dict[ResultsKey.LOCALLY_PRODUCED_RESOURCES] = local_prod_dict
    # Taxes and grid fees
    result_dict[ResultsKey.TAX_PAID] = get_total_tax_paid(job_id=job_id)
    result_dict[ResultsKey.GRID_FEES_PAID] = get_total_grid_fee_paid_on_internal_trades(job_id=job_id)

    logger.info('Saving calculated results')
    save_results(PreCalculatedResults(job_id=job_id, result_dict=result_dict))


def aggregated_local_productions(agents: List[IAgent], net_heat_import: float) -> Dict[str, float]:
    """
    Computing total amount of locally produced resources.
    @return Summed local production by resource name
    """
    production_electricity_lst = []
    production_cooling_lst = []
    # TODO: When changing to Chalmers solver, we'll save the HP production levels for each trading period, and use that
    #  here. But now, as we save heat pump workload, it is messy to calculate, so instead we look at the usage, and then
    #  subtract the net import at the end.
    usage_heating_lst = []
    for agent in agents:
        if isinstance(agent, BlockAgent):
            # TODO: Replace with low-temp and high-temp heat separated
            if agent.digital_twin.total_heating_usage is not None:
                usage_heating_lst.append(sum(agent.digital_twin.total_heating_usage.dropna()))  # Issue with NaNs
            production_electricity_lst.append(sum(agent.digital_twin.electricity_production))
            if agent.digital_twin.cooling_production is not None:
                production_cooling_lst.append(sum(agent.digital_twin.cooling_production))

    production_electricity = sum(production_electricity_lst)
    production_cooling = sum(production_cooling_lst)
    production_heating = sum(usage_heating_lst) - net_heat_import

    return {Resource.ELECTRICITY.name: production_electricity,
            Resource.HEATING.name: production_heating,
            Resource.COOLING.name: production_cooling}
