import logging
import string
from typing import Optional

import pandas as pd

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

from tradingplatformpoc.app.app_threading import StoppableThread
from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator
from tradingplatformpoc.sql.job.crud import get_all_queued_jobs


logger = logging.getLogger(__name__)


class IdPair:
    config_id: str
    job_id: str

    def __init__(self, config_id: str, job_id: str):
        self.config_id = config_id
        self.job_id = job_id


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


def calculate_max_table_height(n_rows: int, max_height: int = 300) -> Optional[int]:
    """
    Ensures that table height is capped at max_height. The returned value is to be passed to `st.table` or
    `st.dataframe` as the "height" argument.
    """
    return max_height if n_rows > 7 else None


def calculate_height_for_no_scroll_up_to(n_rows: int, max_rows_without_scroll: int = 10) -> int:
    """
    If height isn't specified, st.dataframe often annoyingly defaults to just-too-short, so that one has to scroll a
    tiny bit.
    """
    return (min(n_rows, max_rows_without_scroll) + 1) * 35 + 15


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


def cleanup_config_name(name: str) -> str:
    """
    All lower case, replacing blanks with underlines
    """
    return name.lower().strip().replace(' ', '_')


def has_control_characters(input_string: str) -> bool:
    """
    Check if the given input string contains control characters.

    Control characters are non-printable ASCII characters, such as tabs, newlines,
    and other special characters. The function determines if there are any
    characters in the input string that are not part of the printable ASCII characters
    defined by the `string.printable` constant.
    """
    control_characters = set(input_string) - set(string.printable)
    return bool(control_characters)


def config_naming_is_valid(name: str) -> bool:
    """
    Checks that the name of the config is valid - that is, it is not all blanks, and it doesn't contain any control
    characters.
    """
    return (not has_control_characters(name)) and (len(name.replace(' ', '')) > 0)


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
            min-height: 58vh;
        }
        </style>
        """, unsafe_allow_html=True)
