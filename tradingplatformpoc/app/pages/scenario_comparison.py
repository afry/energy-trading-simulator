import logging

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
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
            
    # TODO: Plots and visualizations should go here

else:
    st.markdown('Too few scenarios to compare, set up a configuration in '
                '**Setup simulation** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
