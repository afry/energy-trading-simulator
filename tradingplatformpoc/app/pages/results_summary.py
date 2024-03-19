import logging

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_data_display import build_leaderboard_df
from tradingplatformpoc.sql.results.crud import get_all_results

logger = logging.getLogger(__name__)

show_pages_from_config('tradingplatformpoc/app/pages_config/pages.toml')
add_indentation()

list_of_dicts = get_all_results()
if len(list_of_dicts):
    st.caption("'None' in the below table means that the metric was not calculated, possibly because it was made with "
               "a previous app version. If you want it calculated, navigate to the 'Run simulation' page, delete the "
               "run, and rerun it.")

    df_to_display = build_leaderboard_df(list_of_dicts)
    # If height isn't specified, it annoyingly defaults to just-too-short, so that one has to scroll a tiny bit
    n_rows = len(df_to_display.index)
    st.dataframe(df_to_display, height=(n_rows + 1) * 35 + 15)
else:
    st.markdown('No results to display. Set up a configuration in '
                '**Setup configuration** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
