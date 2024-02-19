import logging
import time

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_charts import construct_avg_day_elec_chart, construct_price_chart
from tradingplatformpoc.app.app_data_display import aggregated_import_and_export_results_df_split_on_period, \
    aggregated_import_and_export_results_df_split_on_temperature, \
    aggregated_net_elec_import_results_df_split_on_period, combine_trades_dfs, construct_combined_price_df, \
    get_price_df_when_local_price_inbetween, resource_dict_to_display_df
from tradingplatformpoc.market.bid import Action, Resource
from tradingplatformpoc.sql.clearing_price.crud import db_to_construct_local_prices_df
from tradingplatformpoc.sql.config.crud import get_all_finished_job_config_id_pairs_in_db, read_config
from tradingplatformpoc.sql.results.crud import get_results_for_job
from tradingplatformpoc.sql.results.models import ResultsKey
from tradingplatformpoc.sql.trade.crud import db_to_aggregated_trade_df

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()

ids = get_all_finished_job_config_id_pairs_in_db()
if len(ids) > 0:
    chosen_config_id_to_view = st.selectbox('Choose a configuration to view results for', ids.keys())
    
    config = read_config(chosen_config_id_to_view)
    job_id = ids[chosen_config_id_to_view]
    pre_calculated_results = get_results_for_job(job_id)

    col_tot_expend, col_empty = st.columns(2)  # SUM_LEC_EXPENDITURE at the top, and nothing in the other column
    with col_tot_expend:
        total_lec_expend = pre_calculated_results[ResultsKey.SUM_LEC_EXPENDITURE]
        st.metric(label="Total energy expenditure",
                  value="{:,.2f} SEK".format(total_lec_expend),
                  help="Total energy spend, minus total income from energy sales, for the local energy community.")

    col_1, col_2 = st.columns(2)
    with col_1:
        total_elec_import = pre_calculated_results[ResultsKey.SUM_NET_IMPORT_ELEC]
        st.metric(label="Total net electricity imported",
                  value="{:,.2f} MWh".format(total_elec_import / 1000))
        total_tax_paid = pre_calculated_results[ResultsKey.TAX_PAID]
        st.metric(label="Total tax paid",
                  value="{:,.2f} SEK".format(total_tax_paid),
                  help="Tax paid includes taxes that the ElectricityGridAgent has paid"
                  " on sales to the microgrid")
    with col_2:
        total_heat_import = pre_calculated_results[ResultsKey.SUM_NET_IMPORT_HEAT]
        st.metric(label="Total net heating imported",
                  value="{:,.2f} MWh".format(total_heat_import / 1000))
        total_grid_fees_paid = pre_calculated_results[ResultsKey.GRID_FEES_PAID]
        st.metric(label="Total grid fees paid on internal trades",
                  value="{:,.2f} SEK".format(total_grid_fees_paid))

    tab_price_graph, tab_price_table = st.tabs(['Graph', 'Table'])
    with tab_price_graph:
        logger.info("Constructing price graph")
        st.spinner("Constructing price graph")

        local_price_df = db_to_construct_local_prices_df(
            job_id=job_id)
        combined_price_df = construct_combined_price_df(local_price_df, config)
        if not combined_price_df.empty:
            price_chart = construct_price_chart(combined_price_df, Resource.ELECTRICITY,)
        st.caption("Click on a variable in legend to highlight it in the graph.")
        st.altair_chart(price_chart, use_container_width=True, theme=None)

        if config['AreaInfo']['LocalMarketEnabled']:
            with tab_price_table:
                st.caption("Periods where local electricity price was "
                           "between external retail and wholesale price:")
                st.dataframe(get_price_df_when_local_price_inbetween(combined_price_df, Resource.ELECTRICITY))
    resources = [Resource.ELECTRICITY, Resource.HEATING]
    agg_tabs = st.tabs([resource.name.capitalize() for resource in resources])
    for resource, tab in zip(resources, agg_tabs):
        with tab:
            if resource == Resource.ELECTRICITY:
                # TODO: Make it possible to choose ex. Dec-Jan
                time_period = st.select_slider('Select which months to view',
                                               options=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                                               value=('Jan', 'Mar'))

                time_period_elec_bought = aggregated_net_elec_import_results_df_split_on_period(job_id, time_period)
                st.caption("Hold *Shift* and click on multiple days in the legend to highlight them in the graph.")
                st.altair_chart(construct_avg_day_elec_chart(time_period_elec_bought, time_period),
                                use_container_width=True, theme=None)
                st.caption("The energy use is calculated from trades, and therefore includes the electricity used \
                           for running heat pumps. The error bars are the standard deviation of the electricity used.")
                st.divider()
                
            agg_buy_trades = db_to_aggregated_trade_df(job_id, resource, Action.BUY)
            agg_sell_trades = db_to_aggregated_trade_df(job_id, resource, Action.SELL)
            # The above can be None if there were no trades for the resource
            agg_trades = combine_trades_dfs(agg_buy_trades, agg_sell_trades)
            if agg_trades is not None:
                agg_trades = agg_trades.transpose().style.set_properties(**{'width': '400px'})
                st.dataframe(agg_trades)

            st.caption("The quantities used for calculations are before losses for purchases but"
                       " after losses for sales.")

    t_start = time.time()
    with st.expander('Total imported and exported electricity and heating:'):  # TODO: Pre-calculate?
        imp_exp_period_dict = aggregated_import_and_export_results_df_split_on_period(job_id)
        imp_exp_temp_dict = aggregated_import_and_export_results_df_split_on_temperature(job_id)
        st.caption("Split on period of year:")
        col1, col2 = st.columns(2)
        col1.header('Imported')
        col2.header("Exported")
        col1.dataframe(imp_exp_period_dict['Imported'])
        col2.dataframe(imp_exp_period_dict['Exported'])
        st.caption("Split on temperature above or below 1 degree Celsius:")
        col1, col2 = st.columns(2)
        col1.dataframe(imp_exp_temp_dict['Imported'])
        col2.dataframe(imp_exp_temp_dict['Exported'])
    t_end = time.time()
    logger.info('Time to display aggregated results: {:.3f} seconds'.format(t_end - t_start))

    with st.expander('Total of locally produced resources:'):
        loc_prod = pre_calculated_results[ResultsKey.LOCALLY_PRODUCED_RESOURCES]
        st.dataframe(resource_dict_to_display_df(loc_prod, 1 / 1000, 'MWh', 'Total'))
            
else:
    st.markdown('No results to view yet, set up a configuration in '
                '**Setup simulation** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
