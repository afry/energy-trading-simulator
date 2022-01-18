from os import write
from tradingplatformpoc.simulation_runner import run_trading_simulations
import logging
import sys

import streamlit as st

# --- Read sys.argv to get logging level, if it is specified ---
string_to_log_later = None
if len(sys.argv) > 1 and type(sys.argv[1]) == str:
    arg_to_upper = str.upper(sys.argv[1])
    try:
        console_log_level = getattr(logging, arg_to_upper)
    except AttributeError:
        # Since we haven't set up the logger yet, will store this message and log it a little bit further down.
        string_to_log_later = "No logging level found with name '{}', console logging level will default to INFO.".\
            format(arg_to_upper)
        console_log_level = logging.INFO
else:
    console_log_level = logging.INFO

# --- Format logger for print statements
FORMAT = "%(asctime)-15s | %(levelname)-7s | %(name)-35.35s | %(message)s"

file_handler = logging.FileHandler("./trading-platform-poc.log")
file_handler.setLevel(logging.DEBUG)  # File logging always DEBUG
stream_handler = logging.StreamHandler()
stream_handler.setLevel(console_log_level)

logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[file_handler, stream_handler]
)

logger = logging.getLogger(__name__)

if string_to_log_later is not None:
    logger.info(string_to_log_later)

if __name__ == '__main__':
    st.write(
        """
        # Prototype data presentation app for energy microgrid trading platform
        
        We want to be able to upload, select and run simulations, and evaluate the results with plots.
        """
    )

    st.sidebar.write("""
    # This is a sidebar where we can have navigation options
    """)
    selection = st.sidebar.selectbox("Options",("Option 1", "Option 2", "Option 3"))

    radio_selection = st.sidebar.radio("Radio options",("radio 1", "radio 2"))
    
    run_sim = st.button("Click here to run simulation")
    if run_sim:
        run_sim = False
        logger.info("Running simulation")
        st.spinner("Running simulation")
        clearing_prices_dict, all_trades_list, all_extra_costs_dict = run_trading_simulations(
        './tradingplatformpoc/data/generated/mock_datas.pickle')
        st.success('Done!')
