import logging
import pickle

import streamlit as st
from tradingplatformpoc.app import footer

from tradingplatformpoc.app.app_functions import construct_price_chart, construct_prices_df
from tradingplatformpoc.bid import Resource

logger = logging.getLogger(__name__)

uploaded_results_file = st.file_uploader(label="Upload results", type="pickle", help="Some help-text")
if uploaded_results_file is not None:
    st.session_state.uploaded_results_file = uploaded_results_file
    logger.info("Reading uploaded results file")
    st.session_state.simulation_results = pickle.load(uploaded_results_file)

load_button = st.button("Click here to load data", disabled='simulation_results' not in st.session_state)

if load_button:
    load_button = False
    
    logger.info("Constructing price graph")
    st.spinner("Constructing price graph")

    st.session_state.combined_price_df = construct_prices_df(st.session_state.simulation_results)
    price_chart = construct_price_chart(st.session_state.combined_price_df, Resource.ELECTRICITY)

    st.session_state.price_chart = price_chart

    st.success("Data loaded!")

st.write(footer.html, unsafe_allow_html=True)
