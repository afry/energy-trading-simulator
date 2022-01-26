from pkg_resources import resource_filename

from tradingplatformpoc import data_store
from tradingplatformpoc.simulation_runner import run_trading_simulations
import logging
import sys

import streamlit as st

import pandas as pd

import altair as alt

# Note: To debug a streamlit script, see https://stackoverflow.com/a/60172283
# This would be neat, but haven't been able to get it to work
# https://altair-viz.github.io/altair-tutorial/notebooks/06-Selections.html#binding-scales-to-other-domains
WHOLESALE_PRICE_STR = 'External wholesale price'
RETAIL_PRICE_STR = 'External retail price'
LOCAL_PRICE_STR = 'Local price'
DATA_PATH = "tradingplatformpoc.data"


@st.cache
def load_data():
    clearing_prices_df = pd.read_csv("clearing_prices.csv")
    clearing_prices_df['period'] = pd.to_datetime(clearing_prices_df['period'])
    clearing_prices_df.rename({'price': LOCAL_PRICE_STR}, axis=1, inplace=True)

    external_price_csv_path = resource_filename(DATA_PATH, "nordpool_area_grid_el_price.csv")
    nordpool_data = data_store.read_nordpool_data(external_price_csv_path)
    nordpool_data.name = 'nordpool'

    both_df = clearing_prices_df.merge(nordpool_data, left_on="period", right_index=True)
    both_df[RETAIL_PRICE_STR] = both_df['nordpool'] + data_store.ELECTRICITY_RETAIL_PRICE_OFFSET
    both_df[WHOLESALE_PRICE_STR] = both_df['nordpool'] + data_store.ELECTRICITY_WHOLESALE_PRICE_OFFSET
    both_df.drop(['nordpool'], axis=1, inplace=True)
    return both_df.melt('period')  # Un-pivot the dataframe from wide to long, which is how Altair prefers it


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

file_handler = logging.FileHandler("./trading-platform-poc.log")
file_handler.setLevel(logging.DEBUG)  # File logging always DEBUG
stream_handler = logging.StreamHandler()
stream_handler.setLevel(console_log_level)

logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[file_handler, stream_handler]
)

logger = logging.getLogger(__name__)

# --- Define path to mock data
mock_datas_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")

if string_to_log_later is not None:
    logger.info(string_to_log_later)


def construct_price_chart():
    domain = [LOCAL_PRICE_STR, RETAIL_PRICE_STR, WHOLESALE_PRICE_STR]
    range_color = ['blue', 'green', 'red']
    range_dash = [[0, 0], [2, 4], [2, 4]]
    return alt.Chart(combined_price_df).mark_line(). \
        encode(x='period',
               y='value',
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               strokeDash=alt.StrokeDash('variable', scale=alt.Scale(domain=domain, range=range_dash))). \
        interactive(bind_y=False)


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

    # These options in the sidebar combined with if clauses can be used to build a
    # multi-page app for more advanced interactions, like switching between experiments
    # or upload/run/analysis pages

    selection = st.sidebar.selectbox("Options", ("Option 1", "Option 2", "Option 3"))

    radio_selection = st.sidebar.radio("Radio options", ("radio 1", "radio 2"))

    run_sim = st.button("Click here to run simulation")
    if run_sim:
        run_sim = False
        logger.info("Running simulation")
        st.spinner("Running simulation")
        clearing_prices_dict, all_trades_list, all_extra_costs_dict = run_trading_simulations(mock_datas_path)
        st.success('Simulation finished!')

    data_button = st.button("Click here to load data")
    if data_button:
        data_button = False
        logger.info("Loading data")
        st.spinner("Loading data")
        combined_price_df = load_data()
        st.success("Data loaded!")

        chart = construct_price_chart()

        st.altair_chart(chart, use_container_width=True)
