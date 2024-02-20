import os
from logging.handlers import TimedRotatingFileHandler

from tradingplatformpoc.app import footer

import logging
import sys

import streamlit as st
from st_pages import show_pages_from_config, add_indentation

from tradingplatformpoc.database import create_db_and_tables, insert_default_config_into_db
from tradingplatformpoc.sql.input_data.crud import insert_input_data_to_db_if_empty
from tradingplatformpoc.sql.input_electricity_price.crud import insert_input_electricity_price_to_db_if_empty

# Note: To debug a streamlit script, see https://stackoverflow.com/a/60172283

# This would be neat, but haven't been able to get it to work
# https://altair-viz.github.io/altair-tutorial/notebooks/06-Selections.html#binding-scales-to-other-domains

# --- Read sys.argv to get logging level, if it is specified ---
string_to_log_later = None
if len(sys.argv) > 1 and type(sys.argv[1]) == str:
    arg_to_upper = str.upper(sys.argv[1])
    try:
        log_level = getattr(logging, arg_to_upper)
    except AttributeError:
        # Since we haven't set up the logger yet, will store this message and log it a little bit further down.
        string_to_log_later = "No logging level found with name '{}', console logging level will default to INFO.". \
            format(arg_to_upper)
        log_level = logging.INFO
else:
    log_level = logging.INFO

# --- Format logger for print statements
FORMAT = "%(asctime)-15s | %(levelname)-7s | %(name)-35.35s | %(message)s"

if not os.path.exists("logfiles"):
    os.makedirs("logfiles")
file_handler = TimedRotatingFileHandler("logfiles/trading-platform-poc.log", when="midnight", interval=1)
file_handler.suffix = "%Y-%m-%d"
file_handler.setLevel(log_level)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(log_level)

logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[file_handler, stream_handler], force=True  # Note that we remove all previously existing handlers here
)

logger = logging.getLogger(__name__)


if string_to_log_later is not None:
    logger.info(string_to_log_later)

create_db_and_tables()
insert_input_data_to_db_if_empty()
insert_input_electricity_price_to_db_if_empty()
insert_default_config_into_db()

if __name__ == '__main__':

    st.set_page_config(layout="wide")

    show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
    add_indentation()

    st.write(
        """
        # Trading platform POC
        ## Prototype data presentation app for energy microgrid trading platform

        **Navigate** by using the sidebar menu to a page
        - *Setup configuration*: Create new scenario configurations
        - *Run simulation*: Run or delete simulations for previously created configurations
        - *Summarized results*: View general results for all scenarios that have been simulated
        - *Detailed results*: View detailed results for one scenario
        - *Results by agent*: View agent-specific results for one scenario
        - *Scenario comparison*: Compare results for two scenarios
        """
    )

    st.write(footer.html, unsafe_allow_html=True)
