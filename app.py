from pkg_resources import resource_filename

from tradingplatformpoc.app.app_constants import ALL_PAGES, BIDS_PAGE, LOAD_PAGE, SELECT_PAGE_RADIO_LABEL, SETUP_PAGE, \
    START_PAGE
from tradingplatformpoc.app.app_functions import construct_price_chart, construct_storage_level_chart, \
    get_price_df_when_local_price_inbetween, load_data
from tradingplatformpoc.bid import Resource
from tradingplatformpoc.simulation_runner import run_trading_simulations
import json
import logging
import sys

import streamlit as st

# Note: To debug a streamlit script, see https://stackoverflow.com/a/60172283

# This would be neat, but haven't been able to get it to work
# https://altair-viz.github.io/altair-tutorial/notebooks/06-Selections.html#binding-scales-to-other-domains

# --- Read sys.argv to get logging level, if it is specified ---
string_to_log_later = None
if len(sys.argv) > 1 and type(sys.argv[1]) == str:
    arg_to_upper = str.upper(sys.argv[1])
    try:
        console_log_level = getattr(logging, arg_to_upper)
    except AttributeError:
        # Since we haven't set up the logger yet, will store this message and log it a little bit further down.
        string_to_log_later = "No logging level found with name '{}', console logging level will default to INFO.". \
            format(arg_to_upper)
        console_log_level = logging.INFO
else:
    console_log_level = logging.INFO

# --- Format logger for print statements
FORMAT = "%(asctime)-15s | %(levelname)-7s | %(name)-35.35s | %(message)s"

file_handler = logging.FileHandler("trading-platform-poc.log")
file_handler.setLevel(logging.DEBUG)  # File logging always DEBUG
stream_handler = logging.StreamHandler()
stream_handler.setLevel(console_log_level)

logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[file_handler, stream_handler]
)

logger = logging.getLogger(__name__)

# --- Define path to mock data and results
mock_datas_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
config_filename = resource_filename("tradingplatformpoc.data", "jonstaka.json")
results_path = "./results/"
with open(config_filename, "r") as jsonfile:
    default_config = json.load(jsonfile)

if string_to_log_later is not None:
    logger.info(string_to_log_later)

if __name__ == '__main__':

    st.sidebar.write("""
    # Navigation
    """)

    page_selected = st.sidebar.radio(SELECT_PAGE_RADIO_LABEL, ALL_PAGES)

    if page_selected == START_PAGE:
        st.write(
            """
            # Prototype data presentation app for energy microgrid trading platform

            We want to be able to upload, select and run simulations, and evaluate the results with plots.
            """
        )
    elif page_selected == SETUP_PAGE:

        run_sim = st.button("Click here to run simulation")
        uploaded_file = st.file_uploader(label="Upload configuration", type="json",
                                                          help="Helptext can go here...")
        st.write("For guidelines on configuration file, see "
                 "https://doc.afdrift.se/display/RPJ/Experiment+configuration")
        st.write("Current experiment configuration:")

        # Want to ensure that if a user uploads a file, moves to another tab in the UI, and then back here, the file
        # hasn't disappeared
        if uploaded_file is not None:
            st.session_state.uploaded_file = uploaded_file
            logger.info("Reading uploaded config file")
            st.session_state.config_data = json.load(st.session_state.uploaded_file)

        if ("config_data" not in st.session_state.keys()) or (st.session_state.config_data is None):
            logger.debug("Using default configuration")
            st.session_state.config_data = default_config

        st.json(st.session_state.config_data)

        if run_sim:
            run_sim = False
            logger.info("Running simulation")
            st.spinner("Running simulation")
            clearing_prices_dict, all_trades_dict, all_extra_costs_dict = run_trading_simulations(st.session_state.
                                                                                                  config_data,
                                                                                                  mock_datas_path,
                                                                                                  results_path)
            st.success('Simulation finished!')

    elif page_selected == LOAD_PAGE:
        data_button = st.button("Click here to load data")
        if data_button:
            data_button = False
            logger.info("Loading data")
            st.spinner("Loading data")
            combined_price_df, bids_df, trades_df, storage_levels = load_data(results_path)
            st.session_state.combined_price_df = combined_price_df
            st.session_state.bids_df = bids_df
            st.session_state.trades_df = trades_df
            st.session_state.storage_levels = storage_levels
            st.session_state.agents_sorted = sorted(bids_df.agent.unique())
            st.success("Data loaded!")

            price_chart = construct_price_chart(combined_price_df, Resource.ELECTRICITY)

            st.session_state.price_chart = price_chart

        if 'price_chart' in st.session_state:
            st.altair_chart(st.session_state.price_chart, use_container_width=True)
            st.write("Periods where local electricity price was between external retail and wholesale price:")
            st.dataframe(get_price_df_when_local_price_inbetween(st.session_state.combined_price_df,
                                                                 Resource.ELECTRICITY))

    elif page_selected == BIDS_PAGE:
        if 'combined_price_df' in st.session_state:
            agent_chosen = st.selectbox(label='Choose agent', options=st.session_state.agents_sorted)
            st.write('Bids for ' + agent_chosen + ':')
            st.dataframe(st.session_state.bids_df.loc[st.session_state.bids_df.agent == agent_chosen].
                         drop(['agent'], axis=1))
            st.write('Trades for ' + agent_chosen + ':')
            st.dataframe(st.session_state.trades_df.loc[st.session_state.trades_df.agent == agent_chosen].
                         drop(['agent'], axis=1))

            if agent_chosen in st.session_state.storage_levels.agent.unique():
                st.write('Charging level over time for ' + agent_chosen + ':')
                storage_chart = construct_storage_level_chart(st.session_state.storage_levels, agent_chosen)
                st.altair_chart(storage_chart, use_container_width=True)
        else:
            st.write('Run simulations and load data first!')
