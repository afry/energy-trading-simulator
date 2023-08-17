import logging
import time

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_visualizations import aggregated_import_and_export_results_df_split_on_period, \
    aggregated_import_and_export_results_df_split_on_temperature, aggregated_local_production_df, \
    construct_combined_price_df, construct_price_chart, \
    get_price_df_when_local_price_inbetween
from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.sql.clearing_price.crud import db_to_construct_local_prices_df
from tradingplatformpoc.sql.config.crud import read_config
from tradingplatformpoc.sql.trade.crud import get_total_grid_fee_paid_on_internal_trades, get_total_tax_paid

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages_subpages.toml")
add_indentation()

if 'choosen_id_to_view' in st.session_state.keys() and st.session_state.choosen_id_to_view is not None:

    col_tax, col_fee = st.columns(2)
    with col_tax:
        st.metric(label="Total tax paid",
                  value="{:,.2f} SEK".format(get_total_tax_paid(
                        job_id=st.session_state.choosen_id_to_view['job_id'])),
                  help="Tax paid includes taxes that the ElectricityGridAgent "
                       "are to pay, on sales to the microgrid.")
    with col_fee:
        st.metric(label="Total grid fees paid on internal trades",
                  value="{:,.2f} SEK".format(get_total_grid_fee_paid_on_internal_trades(
                        job_id=st.session_state.choosen_id_to_view['job_id'])))

    tab_price_graph, tab_price_table = st.tabs(['Graph', 'Table'])
    with tab_price_graph:
        logger.info("Constructing price graph")
        st.spinner("Constructing price graph")

        local_price_df = db_to_construct_local_prices_df(
            job_id=st.session_state.choosen_id_to_view['job_id'])
        combined_price_df = construct_combined_price_df(
            local_price_df, read_config(st.session_state.choosen_id_to_view['config_id']))
        if not combined_price_df.empty:
            st.session_state.combined_price_df = combined_price_df
            price_chart = construct_price_chart(combined_price_df, Resource.ELECTRICITY)
            st.session_state.price_chart = price_chart

        if 'price_chart' in st.session_state:
            st.caption("Click on a variable in legend to highlight it in the graph.")
            st.altair_chart(st.session_state.price_chart, use_container_width=True, theme=None)
        with tab_price_table:
            st.caption("Periods where local electricity price was "
                       "between external retail and wholesale price:")
            st.dataframe(get_price_df_when_local_price_inbetween(st.session_state.combined_price_df,
                                                                 Resource.ELECTRICITY))

if 'simulation_results' in st.session_state:

    t_start = time.time()

    with st.expander('Total imported and exported electricity and heating:'):
        imp_exp_period_dict = aggregated_import_and_export_results_df_split_on_period()
        imp_exp_temp_dict = aggregated_import_and_export_results_df_split_on_temperature()
        col1, col2 = st.columns(2)
        col1.header('Imported')
        col2.header("Exported")
        st.caption("Split on period of year:")
        col1, col2 = st.columns(2)
        col1.dataframe(imp_exp_period_dict['Imported'])
        col2.dataframe(imp_exp_period_dict['Exported'])
        st.caption("Split on temperature above or below 1 degree Celsius:")
        col1, col2 = st.columns(2)
        col1.dataframe(imp_exp_temp_dict['Imported'])
        col2.dataframe(imp_exp_temp_dict['Exported'])

    with st.expander('Total of locally produced heating and electricity:'):
        loc_prod = aggregated_local_production_df()
        st.dataframe(loc_prod)
        st.caption("Total amount of heating produced by local heat pumps "
                   + "and total amount of locally produced electricity.")
    t_end = time.time()
    logger.info('Time to display aggregated results: {:.3f} seconds'.format(t_end - t_start))
            
else:
    st.write('Run simulations and load data first!')

st.write(footer.html, unsafe_allow_html=True)
