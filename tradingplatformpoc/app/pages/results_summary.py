import logging

import pandas as pd

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.sql.results.crud import get_all_results
from tradingplatformpoc.sql.results.models import ResultsKey

logger = logging.getLogger(__name__)

show_pages_from_config('tradingplatformpoc/app/pages_config/pages.toml')
add_indentation()

list_of_dicts = get_all_results()
if len(list_of_dicts):
    df_to_display = pd.DataFrame.from_records(list_of_dicts, index='Config ID')

    # Reorder columns slightly
    first_columns = ['Description', ResultsKey.SUM_LEC_EXPENDITURE,
                     ResultsKey.SUM_NET_IMPORT_HEAT, ResultsKey.SUM_NET_IMPORT_ELEC]
    columns_order = first_columns + [col for col in df_to_display.columns if col not in first_columns]
    df_to_display = df_to_display[columns_order]

    st.dataframe(df_to_display.round(decimals=0))
else:
    st.markdown('No results to display. Set up a configuration in '
                '**Setup configuration** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
