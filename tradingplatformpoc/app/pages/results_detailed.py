import logging

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_charts import construct_avg_day_elec_chart, construct_cooling_machine_chart, \
    construct_price_chart, construct_reservoir_chart
from tradingplatformpoc.app.app_data_display import aggregated_net_elec_import_results_df_split_on_period, \
    build_monthly_stats_df, combine_trades_dfs, construct_combined_price_df, values_by_resource_to_mwh
from tradingplatformpoc.market.trade import Action, Resource, TradeMetadataKey
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

    col_tot_expend, col_empty = st.columns(2)  # NET_ENERGY_SPEND at the top, and nothing in the other column
    with col_tot_expend:
        total_lec_expend = pre_calculated_results[ResultsKey.NET_ENERGY_SPEND]
        st.metric(label="Total net energy spend",
                  value="{:,.2f} SEK".format(total_lec_expend),
                  help="The net energy spend is calculated by subtracting the total revenue from energy exports from "
                       "the total expenditure on importing energy.")

    col_1, col_2 = st.columns(2)
    with col_1:
        total_elec_import = pre_calculated_results[ResultsKey.SUM_NET_IMPORT][Resource.ELECTRICITY.name]
        st.metric(label="Total net electricity imported",
                  value="{:,.2f} MWh".format(total_elec_import / 1000))

        peak_elec_import = pre_calculated_results[ResultsKey.MAX_NET_IMPORT][Resource.ELECTRICITY.name]
        st.metric(label="Peak net electricity imported",
                  value="{:,.2f} MW".format(peak_elec_import / 1000))

        total_tax_paid = pre_calculated_results[ResultsKey.TAX_PAID]
        st.metric(label="Total tax paid",
                  value="{:,.2f} SEK".format(total_tax_paid),
                  help="Tax paid includes taxes that the ElectricityGridAgent has paid"
                  " on sales to the microgrid")
    with col_2:
        total_heat_import = pre_calculated_results[ResultsKey.SUM_NET_IMPORT][Resource.HIGH_TEMP_HEAT.name]
        st.metric(label="Total net heating imported",
                  value="{:,.2f} MWh".format(total_heat_import / 1000))

        peak_heat_import = pre_calculated_results[ResultsKey.MAX_NET_IMPORT][Resource.HIGH_TEMP_HEAT.name]
        st.metric(label="Peak net heating imported",
                  value="{:,.2f} MW".format(peak_heat_import / 1000))

        total_grid_fees_paid = pre_calculated_results[ResultsKey.GRID_FEES_PAID]
        st.metric(label="Total grid fees paid",
                  value="{:,.2f} SEK".format(total_grid_fees_paid))

    with st.expander('Total imported and exported electricity and heating:'):
        col1, col2 = st.columns(2)
        col1.header('Imported')
        col2.header("Exported")
        st.caption("Split on period of year:")
        col1, col2 = st.columns(2)
        total_values_import = pre_calculated_results[ResultsKey.SUM_IMPORT]
        mask_values = pre_calculated_results[ResultsKey.SUM_IMPORT_JAN_FEB]
        col1.dataframe({'Jan-Feb': values_by_resource_to_mwh(mask_values),
                        'Total': values_by_resource_to_mwh(total_values_import)})
        total_values_export = pre_calculated_results[ResultsKey.SUM_EXPORT]
        mask_values = pre_calculated_results[ResultsKey.SUM_EXPORT_JAN_FEB]
        col2.dataframe({'Jan-Feb': values_by_resource_to_mwh(mask_values),
                        'Total': values_by_resource_to_mwh(total_values_export)})
        st.caption("Split on temperature above or below 1 degree Celsius:")
        col1, col2 = st.columns(2)
        below_values = pre_calculated_results[ResultsKey.SUM_IMPORT_BELOW_1_C]
        above_values = {k: total_values_import[k] - v for k, v in below_values.items()}
        col1.dataframe({'Below': values_by_resource_to_mwh(below_values),
                        'Above': values_by_resource_to_mwh(above_values)})
        below_values = pre_calculated_results[ResultsKey.SUM_EXPORT_BELOW_1_C]
        above_values = {k: total_values_export[k] - v for k, v in below_values.items()}
        col2.dataframe({'Below': values_by_resource_to_mwh(below_values),
                        'Above': values_by_resource_to_mwh(above_values)})

    with st.expander('Total of locally produced resources:'):
        res_dict = pre_calculated_results[ResultsKey.LOCALLY_PRODUCED_RESOURCES]
        st.metric(label="Electricity",
                  value="{:,.2f} MWh".format(res_dict[Resource.ELECTRICITY.name] / 1000))
        st.metric(label="Low-tempered heating",
                  value="{:,.2f} MWh".format(res_dict[Resource.LOW_TEMP_HEAT.name] / 1000),
                  help="Heating produced by heat pumps during summer, and excess heat from cooling machines.")
        st.metric(label="High-tempered heating",
                  value="{:,.2f} MWh".format(res_dict[Resource.HIGH_TEMP_HEAT.name] / 1000),
                  help="Heating produced by heat pumps during winter, and booster heat pumps during summer.")

    with st.expander('Unused resources:'):
        heat_dump_chart = construct_reservoir_chart(job_id, TradeMetadataKey.HEAT_DUMP, "Heat")
        if heat_dump_chart is not None:
            st.altair_chart(heat_dump_chart, use_container_width=True, theme=None)
        cool_dump_chart = construct_reservoir_chart(job_id, TradeMetadataKey.COOL_DUMP, "Cooling")
        if cool_dump_chart is not None:
            st.altair_chart(cool_dump_chart, use_container_width=True, theme=None)

    # Resource tabs
    resources = [Resource.ELECTRICITY, Resource.HIGH_TEMP_HEAT, Resource.LOW_TEMP_HEAT, Resource.COOLING]
    agg_tabs = st.tabs([resource.get_display_name(True) for resource in resources])
    for resource, tab in zip(resources, agg_tabs):
        with tab:
            agg_buy_trades = db_to_aggregated_trade_df(job_id, resource, Action.BUY)
            agg_sell_trades = db_to_aggregated_trade_df(job_id, resource, Action.SELL)
            # The above can be None if there were no trades for the resource
            agg_trades = combine_trades_dfs(agg_buy_trades, agg_sell_trades)
            if agg_trades is not None:
                agg_trades = agg_trades.transpose()
                st.dataframe(agg_trades.style.format(precision=2))

            st.caption("The quantities in the table are before losses.")

            if resource in [Resource.HIGH_TEMP_HEAT, Resource.ELECTRICITY]:
                st.subheader("Monthly stats")
                monthly_df = build_monthly_stats_df(pre_calculated_results, resource)
                st.dataframe(monthly_df)

            if resource == Resource.ELECTRICITY:
                st.subheader("Hourly stats")
                time_period = st.select_slider('Select which months to view',
                                               options=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                                        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                                               value=('Jan', 'Mar'))

                time_period_elec_bought = aggregated_net_elec_import_results_df_split_on_period(job_id, time_period)
                if time_period_elec_bought is not None:
                    st.caption("Hold *Shift* and click on multiple days in the legend to highlight them in the graph.")
                    st.altair_chart(construct_avg_day_elec_chart(time_period_elec_bought, time_period),
                                    use_container_width=True, theme=None)
                    st.caption("The energy use is calculated from trades, and therefore includes the electricity used \
                               for running heat pumps. The error bars are the standard deviation of the electricity \
                               used.")
                    st.divider()

                logger.info("Constructing price graph")
                st.spinner("Constructing price graph")

                combined_price_df = construct_combined_price_df(config)
                if not combined_price_df.empty:
                    price_chart = construct_price_chart(combined_price_df, Resource.ELECTRICITY,)
                st.caption("Click on a variable in legend to highlight it in the graph.")
                st.altair_chart(price_chart, use_container_width=True, theme=None)
            elif resource == Resource.COOLING:
                # Show centralized cooling machine production
                cm_chart = construct_cooling_machine_chart(job_id)
                st.altair_chart(cm_chart, use_container_width=True, theme=None)

else:
    st.markdown('No results to view yet, set up a configuration in '
                '**Setup configuration** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
