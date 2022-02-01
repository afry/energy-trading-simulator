from pkg_resources import resource_filename
from streamlit.state.session_state import SessionState

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
START_PAGE = "Start page"
BIDS_PAGE = "Bids"
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

    prices_df = clearing_prices_df.merge(nordpool_data, left_on="period", right_index=True)
    prices_df[RETAIL_PRICE_STR] = prices_df['nordpool'] + data_store.ELECTRICITY_RETAIL_PRICE_OFFSET
    prices_df[WHOLESALE_PRICE_STR] = prices_df['nordpool'] + data_store.ELECTRICITY_WHOLESALE_PRICE_OFFSET
    prices_df.drop(['nordpool'], axis=1, inplace=True)

    all_bids = pd.read_csv("bids.csv")
    all_bids['period'] = pd.to_datetime(all_bids['period'])
    all_bids.drop(['by_external'], axis=1, inplace=True)  # Don't need this column

    return prices_df, all_bids


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


def construct_price_chart(prices_df: pd.DataFrame):
    prices_df = prices_df.melt('period')  # Un-pivot the dataframe from wide to long, which is how Altair prefers it
    domain = [LOCAL_PRICE_STR, RETAIL_PRICE_STR, WHOLESALE_PRICE_STR]
    range_color = ['blue', 'green', 'red']
    range_dash = [[0, 0], [2, 4], [2, 4]]
    return alt.Chart(prices_df).mark_line(). \
        encode(x='period',
               y='value',
               color=alt.Color('variable', scale=alt.Scale(domain=domain, range=range_color)),
               strokeDash=alt.StrokeDash('variable', scale=alt.Scale(domain=domain, range=range_dash))). \
        interactive(bind_y=False)


def get_price_df_when_local_price_inbetween(prices_df: pd.DataFrame) -> pd.DataFrame:
    """Local price is almost always either equal to the external wholesale or retail price. This method returns the
    subsection of the prices dataframe where the local price is _not_ equal to either of these two."""
    price_df_dt_index = prices_df.set_index("period")
    local_price_between_external = (price_df_dt_index[LOCAL_PRICE_STR]
                                    > price_df_dt_index[WHOLESALE_PRICE_STR]
                                    + 0.0001) & (price_df_dt_index[LOCAL_PRICE_STR]
                                                 < price_df_dt_index[RETAIL_PRICE_STR] - 0.0001)
    return price_df_dt_index.loc[local_price_between_external]


if __name__ == '__main__':
    st.write(
        """
        # Prototype data presentation app for energy microgrid trading platform
        
        We want to be able to upload, select and run simulations, and evaluate the results with plots.
        """
    )

    st.sidebar.write("""
    # Navigation
    """)

    page_sel_placeholder = st.sidebar.empty()
    # Will be disabled on startup, and enabled once data has been loaded
    page_selected = page_sel_placeholder.radio("Select page to view", (START_PAGE, BIDS_PAGE),
                                               disabled='combined_price_df' not in st.session_state)

    if page_selected == START_PAGE:
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
            combined_price_df, bids_df = load_data()
            st.session_state.combined_price_df = combined_price_df
            st.session_state.bids_df = bids_df
            st.session_state.agents_sorted = sorted(bids_df.agent.unique())
            st.success("Data loaded!")
            page_selected = page_sel_placeholder.radio("Select page to view", (START_PAGE, BIDS_PAGE), disabled=False)

            price_chart = construct_price_chart(combined_price_df)

            st.session_state.price_chart = price_chart

        if 'price_chart' in st.session_state:
            st.altair_chart(st.session_state.price_chart, use_container_width=True)

    elif page_selected == BIDS_PAGE:
        agent_chosen = st.selectbox(label='Choose agent', options=st.session_state.agents_sorted)

        st.dataframe(st.session_state.bids_df.loc[st.session_state.bids_df.agent == agent_chosen].
                     drop(['agent'], axis=1))
