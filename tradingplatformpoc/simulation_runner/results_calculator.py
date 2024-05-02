import datetime
import logging
from typing import Any, Dict, List, Union

import pandas as pd

from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.grid_agent import GridAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.trade import Action, Resource, TradeMetadataKey
from tradingplatformpoc.sql.extra_cost.crud import db_to_extra_cost_df
from tradingplatformpoc.sql.input_data.crud import read_input_column_df_from_db
from tradingplatformpoc.sql.level.crud import sum_levels
from tradingplatformpoc.sql.results.crud import save_results
from tradingplatformpoc.sql.results.models import PreCalculatedResults, ResultsKey
from tradingplatformpoc.sql.trade.crud import get_external_trades_df, get_total_grid_fee_paid, \
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
                 value_column_name: str = 'quantity_pre_loss'):
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


def calculate_results_and_save(job_id: str, agents: List[IAgent], grid_agents: Dict[Resource, GridAgent]):
    """
    Pre-calculates some results, so that they can be easily fetched later.
    """
    logger.info('Calculating some results')
    result_dict: Dict[str, Any] = {}
    external_trades = get_external_trades_df([job_id])

    extra_costs_sum = get_extra_costs_sum(grid_agents, job_id)

    temperature_df = read_input_column_df_from_db('temperature')
    periods_below_1_c = list(temperature_df[temperature_df['temperature'].values < 1.0].period)

    elec_trades = external_trades[(external_trades.resource == Resource.ELECTRICITY)].copy()
    heat_trades = external_trades[(external_trades.resource == Resource.HIGH_TEMP_HEAT)].copy()
    agg_elec_trades = AggregatedTrades(elec_trades, periods_below_1_c)
    agg_heat_trades = AggregatedTrades(heat_trades, periods_below_1_c)
    result_dict[ResultsKey.NET_ENERGY_SPEND] = (agg_elec_trades.net_energy_spend
                                                + extra_costs_sum
                                                + agg_heat_trades.net_energy_spend)
    result_dict[ResultsKey.SUM_NET_IMPORT] = {Resource.ELECTRICITY.name: agg_elec_trades.sum_net_import,
                                              Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.sum_net_import}
    result_dict[ResultsKey.SUM_IMPORT] = {Resource.ELECTRICITY.name: agg_elec_trades.sum_import,
                                          Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.sum_import}
    result_dict[ResultsKey.SUM_EXPORT] = {Resource.ELECTRICITY.name: agg_elec_trades.sum_export,
                                          Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.sum_export}
    result_dict[ResultsKey.MAX_NET_IMPORT] = {
        Resource.ELECTRICITY.name: max_dict_value(agg_elec_trades.monthly_max_net_import),
        Resource.HIGH_TEMP_HEAT.name: max_dict_value(agg_heat_trades.monthly_max_net_import)}
    result_dict[ResultsKey.MONTHLY_SUM_IMPORT] = {
        Resource.ELECTRICITY.name: agg_elec_trades.monthly_sum_import,
        Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.monthly_sum_import}
    result_dict[ResultsKey.MONTHLY_SUM_EXPORT] = {
        Resource.ELECTRICITY.name: agg_elec_trades.monthly_sum_export,
        Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.monthly_sum_export}
    result_dict[ResultsKey.MONTHLY_SUM_NET_IMPORT] = {
        Resource.ELECTRICITY.name: agg_elec_trades.monthly_sum_net_import,
        Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.monthly_sum_net_import}
    result_dict[ResultsKey.MONTHLY_MAX_NET_IMPORT] = {
        Resource.ELECTRICITY.name: agg_elec_trades.monthly_max_net_import,
        Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.monthly_max_net_import}
    # Aggregated import/export, split on period/temperature
    result_dict[ResultsKey.SUM_IMPORT_JAN_FEB] = {Resource.ELECTRICITY.name: agg_elec_trades.sum_import_jan_feb,
                                                  Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.sum_import_jan_feb}
    result_dict[ResultsKey.SUM_EXPORT_JAN_FEB] = {Resource.ELECTRICITY.name: agg_elec_trades.sum_export_jan_feb,
                                                  Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.sum_export_jan_feb}
    result_dict[ResultsKey.SUM_IMPORT_BELOW_1_C] = {Resource.ELECTRICITY.name: agg_elec_trades.sum_import_below_1_c,
                                                    Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.sum_import_below_1_c}
    result_dict[ResultsKey.SUM_EXPORT_BELOW_1_C] = {Resource.ELECTRICITY.name: agg_elec_trades.sum_export_below_1_c,
                                                    Resource.HIGH_TEMP_HEAT.name: agg_heat_trades.sum_export_below_1_c}
    # Aggregated local production
    local_prod_dict = aggregated_local_productions(agents, job_id)
    result_dict[ResultsKey.LOCALLY_PRODUCED_RESOURCES] = local_prod_dict
    # Taxes and grid fees
    result_dict[ResultsKey.TAX_PAID] = get_total_tax_paid(job_id=job_id)
    result_dict[ResultsKey.GRID_FEES_PAID] = get_total_grid_fee_paid(job_id=job_id)
    # Resources dumped into reservoir
    result_dict[ResultsKey.HEAT_DUMPED] = sum_levels(job_id, TradeMetadataKey.HEAT_DUMP.name)
    result_dict[ResultsKey.COOL_DUMPED] = sum_levels(job_id, TradeMetadataKey.COOL_DUMP.name)

    save_results(PreCalculatedResults(job_id=job_id, result_dict=result_dict))


def max_dict_value(some_dict: Dict[Any, Union[int, float]]) -> Union[int, float]:
    """Returns the maximum value, if there are any values present, else returns 0."""
    return max(some_dict.values()) if some_dict else 0


def get_extra_costs_sum(grid_agents: Dict[Resource, GridAgent], job_id: str) -> float:
    extra_costs = db_to_extra_cost_df(job_id)
    if len(extra_costs) > 0:
        extra_costs = extra_costs[~extra_costs['agent'].isin([x.guid for x in grid_agents.values()])]
        extra_costs_sum = extra_costs['cost'].sum()
        return extra_costs_sum
    return 0.0


def aggregated_local_productions(agents: List[IAgent], job_id: str) -> Dict[str, float]:
    """
    Computing total amount of locally produced resources.
    @return Summed local production by resource name
    """
    hp_high_heat_prod = sum_levels(job_id, TradeMetadataKey.HP_HIGH_HEAT_PROD.name)
    hp_low_heat_prod = sum_levels(job_id, TradeMetadataKey.HP_LOW_HEAT_PROD.name)
    cm_low_heat_prod = sum_levels(job_id, TradeMetadataKey.CM_HEAT_PROD.name)

    production_electricity_lst = []
    production_low_temp_heat_lst = []
    for agent in agents:
        if isinstance(agent, BlockAgent):
            if agent.digital_twin.electricity_production is not None:
                production_electricity_lst.append(sum(agent.digital_twin.electricity_production))
            if agent.digital_twin.space_heating_production is not None:
                production_low_temp_heat_lst.append(sum(agent.digital_twin.space_heating_production))
    return {Resource.ELECTRICITY.name: sum(production_electricity_lst),
            Resource.HIGH_TEMP_HEAT.name: hp_high_heat_prod,
            Resource.LOW_TEMP_HEAT.name: sum(production_low_temp_heat_lst) + hp_low_heat_prod + cm_low_heat_prod}
