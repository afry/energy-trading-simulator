import json
import logging

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_functions import load_results

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages_subpages.toml")
add_indentation()

uploaded_results_file = st.file_uploader(label="Upload results", type="pickle", help="Some help-text")
if uploaded_results_file is not None:
    logger.info("Reading uploaded results file")
    st.session_state.uploaded_results_file = uploaded_results_file

load_button = st.button("Click here to load data", disabled=('uploaded_results_file' not in st.session_state))

if load_button:
    load_button = False
    if uploaded_results_file is not None:
        load_results(uploaded_results_file)
        st.success("Data loaded!")
    elif 'uploaded_results_file' in st.session_state:
        st.info(" ".join(["Data already loaded from", st.session_state.uploaded_results_file.name]))

    with st.expander('Simulation configuration used, in JSON format:'):
        st.json(body=json.dumps(st.session_state.simulation_results.config_data))

elif ('uploaded_results_file' in st.session_state) and ('simulation_results' in st.session_state):
    if uploaded_results_file is None:
        st.success(" ".join(["Currently using data loaded from:", st.session_state.uploaded_results_file.name]))
    else:
        st.info("To replace previously loaded results with results from file, press load button.")

    with st.expander('Simulation configuration used, in JSON format:'):
        st.json(body=json.dumps(st.session_state.simulation_results.config_data))

st.write(footer.html, unsafe_allow_html=True)
