import datetime
import logging
import os
import pickle
from typing import Tuple

import pandas as pd

import streamlit as st

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.compress import bz2_compress_pickle, bz2_decompress_pickle
from tradingplatformpoc.constants import MOCK_DATA_PATH
from tradingplatformpoc.results.simulation_results import SimulationResults
from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator


logger = logging.getLogger(__name__)


# ------------------------------------- Save result functions ---------------------------------
def set_simulation_results(simulation_results: SimulationResults):
    """Writes simulation results to file."""
    data = (datetime.datetime.now(datetime.timezone.utc), simulation_results)
    bz2_compress_pickle(app_constants.LAST_SIMULATION_RESULTS, data)


def read_simulation_results() -> Tuple[datetime.datetime, SimulationResults]:
    """Reads simulation results from file."""

    return bz2_decompress_pickle(app_constants.LAST_SIMULATION_RESULTS)


def results_button(results_download_button):
    if os.path.exists(app_constants.LAST_SIMULATION_RESULTS):
        last_simultion_timestamp, last_simultion_results = read_simulation_results()
        results_download_button.download_button(label="Download simulation result from :green["
                                                + last_simultion_timestamp.strftime("%Y-%m-%d, %H:%M") + " UTC]",
                                                help="Download simulation result from last run that was finished at "
                                                + last_simultion_timestamp.strftime("%Y-%m-%d, %H:%M") + " UTC",
                                                data=pickle.dumps(last_simultion_results),
                                                file_name="simulation_results_"
                                                + last_simultion_timestamp.strftime("%Y%m%d%H%M") + ".pickle",
                                                mime='application/octet-stream')
    else:
        results_download_button.download_button(label="Download simulation results", data=b'placeholder',
                                                disabled=True)
# ----------------------------------- End save result functions -------------------------------


def set_max_width(width: str):
    """
    Sets the max width of the page. The input can be specified either in pixels (i.e. "500px") or as a percentage (i.e.
    "50%").
    Taken from https://discuss.streamlit.io/t/where-to-set-page-width-when-set-into-non-widescreeen-mode/959/16.
    """
    st.markdown(f"""
    <style>
    .appview-container .main .block-container{{ max-width: {width}; }}
    </style>
    """, unsafe_allow_html=True, )


# @st.cache_data(ttl=3600)
def convert_df_to_csv(df: pd.DataFrame, include_index: bool = False):
    return df.to_csv(index=include_index).encode('utf-8')


def download_df_as_csv_button(df: pd.DataFrame, file_name: str, include_index: bool = False):
    csv = convert_df_to_csv(df, include_index=include_index)
    st.download_button(label='Download as csv',
                       data=csv,
                       file_name=file_name + ".csv")
    

# @st.cache_data()
def load_results(uploaded_results_file):
    st.session_state.simulation_results = pickle.load(uploaded_results_file)


def update_multiselect_style():
    st.markdown(
        """
        <style>
            .stMultiSelect [data-baseweb="tag"] {
                height: fit-content;
                background-color: white !important;
                color: black;
            }
            .stMultiSelect [data-baseweb="tag"] span[title] {
                white-space: normal; max-width: 100%; overflow-wrap: anywhere;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def run_simulation(choosen_config_id: str):
    logger.info("Running simulation")
    simulator = TradingSimulator(choosen_config_id, MOCK_DATA_PATH)
    simulation_results = simulator()
    if simulation_results is not None:
        set_simulation_results(simulation_results)
        st.session_state.simulation_results = simulation_results
        logger.info("Simulation finished!")
        st.success('Simulation finished!')
        # results_button(results_download_button)
    else:
        logger.error("Simulation could not finish!")
        # TODO: Delete job ID
        st.error("Simulation could not finish!")
