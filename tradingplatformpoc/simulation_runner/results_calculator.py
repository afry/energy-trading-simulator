import logging
from typing import Dict, List

import pandas as pd

from tradingplatformpoc.agent.block_agent import BlockAgent
from tradingplatformpoc.agent.iagent import IAgent
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.sql.results.crud import save_results
from tradingplatformpoc.sql.results.models import PreCalculatedResults, ResultsKey
from tradingplatformpoc.sql.trade.crud import get_external_trades_df, get_total_grid_fee_paid_on_internal_trades, \
    get_total_tax_paid

logger = logging.getLogger(__name__)


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


def calculate_results_and_save(job_id: str, agents: List[IAgent]):
    """Pre-calculates some results, so that they can be easily fetched later."""
    logger.info('Calculating some results...')
    result_dict = {ResultsKey.TAX_PAID: get_total_tax_paid(job_id=job_id),
                   ResultsKey.GRID_FEES_PAID: get_total_grid_fee_paid_on_internal_trades(job_id=job_id)}
    df = get_external_trades_df([job_id])
    col_names_needed = ['period', 'action', 'price', 'quantity_post_loss']
    elec_trades = df[(df.resource == Resource.ELECTRICITY)][col_names_needed]
    heat_trades = df[(df.resource == Resource.HEATING)][col_names_needed]
    agg_elec_trades = AggregatedTrades(elec_trades)
    agg_heat_trades = AggregatedTrades(heat_trades)
    result_dict[ResultsKey.SUM_NET_IMPORT_ELEC] = agg_elec_trades.sum_net_import
    # Converting pd.Series to dicts here, to make them JSON-serializable
    result_dict[ResultsKey.MONTHLY_SUM_NET_IMPORT_ELEC] = agg_elec_trades.monthly_sum_net_import.to_dict()
    result_dict[ResultsKey.MONTHLY_MAX_NET_IMPORT_ELEC] = agg_elec_trades.monthly_max_net_import.to_dict()
    result_dict[ResultsKey.SUM_NET_IMPORT_HEAT] = agg_heat_trades.sum_net_import
    # Converting pd.Series to dicts here, to make them JSON-serializable
    result_dict[ResultsKey.MONTHLY_SUM_NET_IMPORT_HEAT] = agg_heat_trades.monthly_sum_net_import.to_dict()
    result_dict[ResultsKey.MONTHLY_MAX_NET_IMPORT_HEAT] = agg_heat_trades.monthly_max_net_import.to_dict()
    result_dict[ResultsKey.SUM_LEC_EXPENDITURE] = (agg_elec_trades.sum_lec_expenditure
                                                   + agg_heat_trades.sum_lec_expenditure)
    # Aggregated local production
    loc_prod = aggregated_local_production_df(agents, agg_heat_trades.sum_net_import)
    result_dict[ResultsKey.LOCALLY_PRODUCED_RESOURCES] = loc_prod
    save_results(PreCalculatedResults(job_id=job_id, result_dict=result_dict))


def aggregated_local_production_df(agents: List[IAgent], net_heat_import: float) -> Dict[str, float]:
    """
    Computing total amount of locally produced resources.
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

    return {Resource.ELECTRICITY.get_display_name(): production_electricity,
            Resource.COOLING.get_display_name(): production_cooling,
            Resource.HEATING.get_display_name(): production_heating}
