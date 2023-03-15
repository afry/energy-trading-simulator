import logging

import streamlit as st
from tradingplatformpoc.app import footer

from tradingplatformpoc.app.app_functions import load_results

logger = logging.getLogger(__name__)

uploaded_results_file = st.file_uploader(label="Upload results", type="pickle", help="Some help-text")

load_button = st.button("Click here to load data", disabled=(uploaded_results_file is None))

if load_button:
    load_button = False
    if uploaded_results_file is not None:
        logger.info("Reading uploaded results file")
        load_results(uploaded_results_file)
        st.success("Data loaded!")
elif 'simulation_results' in st.session_state:
    st.success(" ".join(["Currently using data loaded from:", st.session_state.uploaded_results_file.name]))

st.write(footer.html, unsafe_allow_html=True)
