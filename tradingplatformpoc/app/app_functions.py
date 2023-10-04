
import logging

import pandas as pd

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

from tradingplatformpoc.app.app_threading import StoppableThread
from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator
from tradingplatformpoc.sql.job.crud import get_all_queued_jobs


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


def color_in(val):
    if 'Running' in val:
        color = '#f7a34f'
    elif 'Pending' in val:
        color = '#0675bb'
    elif 'Completed' in val:
        color = '#5eab7e'
    else:
        color = '#f01d5c'
    return 'color: %s' % color

    
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


def run_simulation(job_id: str):
    logger.info("Running simulation")
    simulator = TradingSimulator(job_id)
    simulator()
    # TODO: Functionality to shut down job
    # TODO: Delete job is not finished?
    # TODO: Add functionality to schedule removal of potential uncompleted jobs


def run_next_job_in_queue() -> bool:
    queue = get_all_queued_jobs()
    if len(queue) > 0:
        job_id = queue[0]
        logger.info('Running job with ID {}'.format(job_id))
        t = StoppableThread(name='run_' + job_id, target=run_simulation, args=(job_id,))
        add_script_run_ctx(t)
        t.start()
        return True
    else:
        logger.debug('No jobs in queue.')
        return False


def make_room_for_menu_in_sidebar():
    st.sidebar.markdown("""
        <style>
        [data-testid='stSidebarNav'] > ul {
            min-height: 47vh;
        }
        </style>
        """, unsafe_allow_html=True)
