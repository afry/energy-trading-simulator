import logging

import pandas as pd

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.sql.results.crud import get_all_results

logger = logging.getLogger(__name__)

show_pages_from_config('tradingplatformpoc/app/pages_config/pages.toml')
add_indentation()

list_of_dicts = get_all_results()
df_to_display = pd.DataFrame.from_records(list_of_dicts, index='Config ID')
st.dataframe(df_to_display.round(decimals=0))
st.caption('All values in SEK or kWh.')
