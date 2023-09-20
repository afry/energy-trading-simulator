import logging

import pandas as pd

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import app_constants, footer
from tradingplatformpoc.app.app_visualizations import construct_price_chart
from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.sql.clearing_price.crud import db_to_construct_local_prices_df
from tradingplatformpoc.sql.config.crud import get_all_finished_job_config_id_pairs_in_db

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()

ids = get_all_finished_job_config_id_pairs_in_db()
if len(ids) >= 2:
    first_col, second_col = st.columns(2)
    with first_col:
        chosen_config_id_to_view_1 = st.selectbox('Choose a first configuration to compare', ids.keys())
        if chosen_config_id_to_view_1 is not None:
            st.session_state.chosen_config_id_to_view_1 = {'config_id': chosen_config_id_to_view_1,
                                                           'job_id': ids[chosen_config_id_to_view_1]}
    with second_col:
        chosen_config_id_to_view_2 = st.selectbox(
            'Choose a second configuration to compare',
            [key for key in ids.keys() if key != st.session_state.chosen_config_id_to_view_1['config_id']])
        if chosen_config_id_to_view_2 is not None:
            st.session_state.chosen_config_id_to_view_2 = {'config_id': chosen_config_id_to_view_2,
                                                           'job_id': ids[chosen_config_id_to_view_2]}
            
    if ('chosen_config_id_to_view_1' in st.session_state.keys()) \
       and ('chosen_config_id_to_view_2' in st.session_state.keys()):
        # Price graph
        logger.info("Constructing price graph")
        st.spinner("Constructing price graph")

        local_price_df_1 = db_to_construct_local_prices_df(
            job_id=st.session_state.chosen_config_id_to_view_1['job_id'])
        local_price_df_1['variable'] = app_constants.LOCAL_PRICE_STR \
            + ' ' + st.session_state.chosen_config_id_to_view_1['config_id']
        local_price_df_2 = db_to_construct_local_prices_df(
            job_id=st.session_state.chosen_config_id_to_view_2['job_id'])
        local_price_df_2['variable'] = app_constants.LOCAL_PRICE_STR \
            + ' ' + st.session_state.chosen_config_id_to_view_2['config_id']
        combined_price_df = pd.concat([local_price_df_1, local_price_df_2])
        price_chart = construct_price_chart(
            combined_price_df,
            Resource.ELECTRICITY,
            [app_constants.LOCAL_PRICE_STR + ' ' + st.session_state.chosen_config_id_to_view_1['config_id'],
             app_constants.LOCAL_PRICE_STR + ' ' + st.session_state.chosen_config_id_to_view_2['config_id']],
            ['blue', 'green'],
            [[0, 0], [2, 4]])
        st.caption("Click on a variable in legend to highlight it in the graph.")
        st.altair_chart(price_chart, use_container_width=True, theme=None)

else:
    st.markdown('Too few scenarios to compare, set up a configuration in '
                '**Setup simulation** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
