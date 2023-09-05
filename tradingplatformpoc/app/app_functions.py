
import logging

import pandas as pd

import streamlit as st

from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator


logger = logging.getLogger(__name__)


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


def run_simulation(chosen_config_id: str):
    logger.info("Running simulation")
    simulator = TradingSimulator(chosen_config_id)
    simulator()
    # TODO: Functionality to shut down job
    # TODO: Delete job is not finished?
    # TODO: Add functionality to schedule removal of potential uncompleted jobs

    
def cleanup_config_description(description: str) -> str:
    """
    Checks that the description of the config is valid.
    """
    description = description.lower().strip().capitalize()
    if not description[-1] == ".":
        description = description + "."
    return description


def cleanup_config_name(name: str) -> str:
    """
    Checks that the name of the config is valid.
    """
    return name.lower().strip().replace(' ', '_')


def config_naming_is_valid(name: str) -> bool:
    return name.replace(' ', '').isalpha() and (len(name.replace(' ', '')) > 0)
