import logging
import time
import streamlit as st
from st_pages import show_pages_from_config, add_indentation
from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_visualizations import aggregated_import_and_export_results_df_split_on_period, \
    aggregated_import_and_export_results_df_split_on_temperature, aggregated_local_production_df, \
    aggregated_taxes_and_fees_results_df, construct_price_chart, construct_prices_df, \
    get_price_df_when_local_price_inbetween

from tradingplatformpoc.bid import Resource

logger = logging.getLogger(__name__)

show_pages_from_config("pages_config/pages_subpages.toml")
add_indentation()

if 'simulation_results' in st.session_state:

    logger.info("Constructing price graph")
    st.spinner("Constructing price graph")

    st.session_state.combined_price_df = construct_prices_df(st.session_state.simulation_results)
    price_chart = construct_price_chart(st.session_state.combined_price_df, Resource.ELECTRICITY)

    st.session_state.price_chart = price_chart

    t_start = time.time()
    with st.expander('Taxes and fees on internal trades:'):
        tax_fee = aggregated_taxes_and_fees_results_df()
        st.dataframe(tax_fee)
        st.caption("Tax paid includes taxes that the ElectricityGridAgent "
                   "are to pay, on sales to the microgrid.")

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

    if 'price_chart' in st.session_state:
        st.altair_chart(st.session_state.price_chart, use_container_width=True, theme=None)
        with st.expander("Periods where local electricity price was "
                         "between external retail and wholesale price:"):
            st.dataframe(get_price_df_when_local_price_inbetween(st.session_state.combined_price_df,
                                                                 Resource.ELECTRICITY))
else:
    st.write('Run simulations and load data first!')

st.write(footer.html, unsafe_allow_html=True)
