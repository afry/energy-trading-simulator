import logging

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.sql.config.crud import get_all_finished_job_config_id_pairs_in_db, read_config

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages_subpages.toml")
add_indentation()

ids = get_all_finished_job_config_id_pairs_in_db()
if len(ids) > 0:
    chosen_config_id_to_view = st.selectbox('Choose a configuration to view results for', ids.keys())
    if chosen_config_id_to_view is not None:
        st.session_state.chosen_id_to_view = {'config_id': chosen_config_id_to_view,
                                              'job_id': ids[chosen_config_id_to_view]}
        with st.expander('Configuration *{}* in JSON format'.format(st.session_state.chosen_id_to_view['config_id'])):
            st.json(read_config(st.session_state.chosen_id_to_view['config_id']), expanded=True)
else:
    st.markdown('No results to view yet, set up a configuration in '
                '**Setup simulation** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
