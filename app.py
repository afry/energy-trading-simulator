from pkg_resources import resource_filename

from tradingplatformpoc.app import app_constants
from tradingplatformpoc.app.app_functions import add_building_agent, add_grid_agent, add_grocery_store_agent, \
    add_pv_agent, add_storage_agent, construct_price_chart, construct_storage_level_chart, \
    get_price_df_when_local_price_inbetween, load_data, remove_agent, remove_all_building_agents
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
from tradingplatformpoc.trading_platform_utils import ALL_AGENT_TYPES, get_if_exists_else, ALL_IMPLEMENTED_RESOURCES_STR

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
    handlers=[file_handler, stream_handler], force=True  # Note that we remove all previously existing handlers here
)

logger = logging.getLogger(__name__)

# --- Define path to mock data and results
mock_datas_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
config_filename = resource_filename("tradingplatformpoc.data", "default_config.json")
results_path = "./results/"
with open(config_filename, "r") as jsonfile:
    default_config = json.load(jsonfile)

if string_to_log_later is not None:
    logger.info(string_to_log_later)

if __name__ == '__main__':

    st.set_page_config(page_title="Trading platform POC")

    st.sidebar.write("""
    # Navigation
    """)

    page_selected = st.sidebar.radio(app_constants.SELECT_PAGE_RADIO_LABEL, app_constants.ALL_PAGES)

    if page_selected == app_constants.START_PAGE:
        st.write(
            """
            # Prototype data presentation app for energy microgrid trading platform

            We want to be able to upload, select and run simulations, and evaluate the results with plots.
            """
        )
    elif page_selected == app_constants.SETUP_PAGE:

        run_sim = st.button("Click here to run simulation")

        if ("config_data" not in st.session_state.keys()) or (st.session_state.config_data is None):
            logger.debug("Using default configuration")
            st.session_state.config_data = default_config

        # --------------------- Start config specification for dummies ------------------------
        # Could perhaps save the config to a temporary file on-change of these? That way changes won't get lost
        st.subheader("General area parameters:")
        st.session_state.config_data['AreaInfo']['DefaultPVEfficiency'] = st.number_input(
            'Default PV efficiency:', min_value=0.01, max_value=0.99, format='%.3f',
            value=st.session_state.config_data['AreaInfo']['DefaultPVEfficiency'],
            help=app_constants.DEFAULT_PV_EFFICIENCY_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ExternalElectricityWholesalePriceOffset'] = st.number_input(
            'External electricity wholesale price offset:', min_value=-1.0, max_value=1.0,
            value=st.session_state.config_data['AreaInfo']['ExternalElectricityWholesalePriceOffset'],
            help=app_constants.ELECTRICITY_WHOLESALE_PRICE_OFFSET_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ExternalElectricityRetailPriceOffset'] = st.number_input(
            'External electricity retail price offset:', min_value=-1.0, max_value=1.0,
            value=st.session_state.config_data['AreaInfo']['ExternalElectricityRetailPriceOffset'],
            help=app_constants.ELECTRICITY_RETAIL_PRICE_OFFSET_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'] = st.number_input(
            'External heating wholesale price fraction:', min_value=0.0, max_value=1.0,
            value=st.session_state.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'],
            help=app_constants.HEATING_WHOLESALE_PRICE_FRACTION_HELP_TEXT)

        # Start agents
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Agents:")
        with col2:
            st.button("Remove all BuildingAgents", on_click=remove_all_building_agents)

        for agent in st.session_state.config_data['Agents'][:]:
            with st.expander(agent['Name']):
                agent['Name'] = st.text_input('Name', value=agent['Name'])
                agent['Type'] = st.selectbox('Type', options=ALL_AGENT_TYPES,
                                             key='TypeSelectBox' + agent['Name'],
                                             index=ALL_AGENT_TYPES.index(agent['Type']))
                if agent['Type'] == 'BuildingAgent':
                    agent['RandomSeed'] = int(st.number_input(
                        'Random seed',
                        value=int(agent['RandomSeed']),
                        help=app_constants.RANDOM_SEED_HELP_TEXT,
                        key='RandomSeed' + agent['Name']
                    ))
                    agent['GrossFloorArea'] = st.number_input(
                        'Gross floor area (sqm)', min_value=0.0,
                        value=float(agent['GrossFloorArea']),
                        help=app_constants.GROSS_FLOOR_AREA_HELP_TEXT,
                        key='GrossFloorArea' + agent['Name']
                    )
                    agent['FractionCommercial'] = st.number_input(
                        'Fraction commercial', min_value=0.0, max_value=1.0,
                        value=get_if_exists_else(agent, 'FractionCommercial', 0.0),
                        help=app_constants.FRACTION_COMMERCIAL_HELP_TEXT,
                        key='FractionCommercial' + agent['Name']
                    )
                    agent['FractionSchool'] = st.number_input(
                        'Fraction school', min_value=0.0, max_value=1.0,
                        value=get_if_exists_else(agent, 'FractionSchool', 0.0),
                        help=app_constants.FRACTION_SCHOOL_HELP_TEXT,
                        key='FractionSchool' + agent['Name']
                    )
                if agent['Type'] in ['StorageAgent', 'GridAgent']:
                    agent['Resource'] = st.selectbox('Resource', options=ALL_IMPLEMENTED_RESOURCES_STR,
                                                     key='ResourceSelectBox' + agent['Name'],
                                                     index=ALL_IMPLEMENTED_RESOURCES_STR.index(agent['Resource']))
                if agent['Type'] == 'StorageAgent':
                    agent['Capacity'] = st.number_input(
                        'Capacity', min_value=0.0, step=1.0,
                        value=float(agent['Capacity']),
                        help=app_constants.CAPACITY_HELP_TEXT,
                        key='Capacity' + agent['Name']
                    )
                    agent['ChargeRate'] = st.number_input(
                        'Charge rate', min_value=0.01, max_value=10.0,
                        value=float(agent['ChargeRate']),
                        help=app_constants.CHARGE_RATE_HELP_TEXT,
                        key='ChargeRate' + agent['Name']
                    )
                    agent['RoundTripEfficiency'] = st.number_input(
                        'Round-trip efficiency', min_value=0.01, max_value=1.0,
                        value=float(agent['RoundTripEfficiency']),
                        help=app_constants.ROUND_TRIP_EFFICIENCY_HELP_TEXT,
                        key='RoundTripEfficiency' + agent['Name']
                    )
                    agent['NHoursBack'] = int(st.number_input(
                        '\'N hours back\'', min_value=1, max_value=8760,
                        value=int(agent['NHoursBack']),
                        help=app_constants.N_HOURS_BACK_HELP_TEXT,
                        key='NHoursBack' + agent['Name']
                    ))
                    agent['BuyPricePercentile'] = st.number_input(
                        '\'Buy-price percentile\'', min_value=0.0, max_value=100.0, step=1.0,
                        value=float(agent['BuyPricePercentile']),
                        help=app_constants.BUY_PERC_HELP_TEXT,
                        key='BuyPricePercentile' + agent['Name']
                    )
                    agent['SellPricePercentile'] = st.number_input(
                        '\'Sell-price percentile\'', min_value=0.0, max_value=100.0, step=1.0,
                        value=float(agent['SellPricePercentile']),
                        help=app_constants.SELL_PERC_HELP_TEXT,
                        key='SellPricePercentile' + agent['Name']
                    )
                    agent['DischargeRate'] = st.number_input(
                        'Discharge rate', min_value=0.01, max_value=10.0,
                        value=float(get_if_exists_else(agent, 'DischargeRate', agent['ChargeRate'])),
                        help=app_constants.DISCHARGE_RATE_HELP_TEXT,
                        key='DischargeRate' + agent['Name']
                    )
                if agent['Type'] in ['BuildingAgent', 'PVAgent', 'GroceryStoreAgent']:
                    agent['PVArea'] = st.number_input(
                        'PV area (sqm)', min_value=0.0, format='%.1f', step=1.0,
                        value=float(get_if_exists_else(agent, 'PVArea', 0.0)),
                        help=app_constants.PV_AREA_HELP_TEXT,
                        key='PVArea' + agent['Name']
                    )
                    agent['PVEfficiency'] = st.number_input(
                        'PV efficiency', min_value=0.01, max_value=0.99, format='%.3f',
                        value=get_if_exists_else(agent, 'PVEfficiency',
                                                 st.session_state.config_data['AreaInfo']['DefaultPVEfficiency']),
                        help=app_constants.PV_EFFICIENCY_HELP_TEXT,
                        key='PVEfficiency' + agent['Name']
                    )
                if agent['Type'] == 'GridAgent':
                    agent['TransferRate'] = st.number_input(
                        'Transfer rate', min_value=0.0, step=10.0,
                        value=float(agent['TransferRate']),
                        help=app_constants.TRANSFER_RATE_HELP_TEXT,
                        key='TransferRate' + agent['Name']
                    )
                remove_agent_button = st.button('Remove agent', key='RemoveButton' + agent['Name'],
                                                on_click=remove_agent, args=(agent,))
        # Buttons to add agents
        col1, col2, col3 = st.columns(3)

        # Annoyingly, these buttons have different sizes depending on the amount of text in them.
        # Can use CSS to customize buttons but that then applies to all buttons on the page, so will leave as is
        with col1:
            add_building_agent_button = st.button("Add BuildingAgent", on_click=add_building_agent)
            add_grocery_store_agent_button = st.button("Add GroceryStoreAgent", on_click=add_grocery_store_agent)
        with col2:
            add_storage_agent_button = st.button("Add StorageAgent", on_click=add_storage_agent)
            add_grid_agent_button = st.button("Add GridAgent", on_click=add_grid_agent)
        with col3:
            add_pv_agent_button = st.button("Add PVAgent", on_click=add_pv_agent)

        # --------------------- End config specification for dummies ------------------------

        st.subheader("Current configuration in JSON format:")
        st.json(st.session_state.config_data)
        uploaded_file = st.file_uploader(label="Upload configuration", type="json",
                                         help="Expand the sections below for information on how the configuration file "
                                              "should look")
        with st.expander("Guidelines on configuration file"):
            st.markdown(app_constants.CONFIG_GUIDELINES_MARKDOWN)
            st.json(app_constants.AREA_INFO_EXAMPLE)
        with st.expander("BuildingAgent specification"):
            st.markdown(app_constants.BUILDING_AGENT_SPEC_MARKDOWN)
            st.json(app_constants.BUILDING_AGENT_EXAMPLE)
        with st.expander("StorageAgent specification"):
            st.markdown(app_constants.STORAGE_AGENT_SPEC_MARKDOWN)
            st.json(app_constants.STORAGE_AGENT_EXAMPLE)
        with st.expander("GridAgent specification"):
            st.markdown(app_constants.GRID_AGENT_SPEC_MARKDOWN)
            st.json(app_constants.GRID_AGENT_EXAMPLE)
        with st.expander("PVAgent specification"):
            st.markdown(app_constants.PV_AGENT_SPEC_MARKDOWN)
            st.json(app_constants.PV_AGENT_EXAMPLE)
        with st.expander("GroceryStoreAgent specification"):
            st.markdown(app_constants.GROCERY_STORE_AGENT_SPEC_MARKDOWN)
            st.json(app_constants.GROCERY_STORE_AGENT_EXAMPLE)

        # Want to ensure that if a user uploads a file, moves to another tab in the UI, and then back here, the file
        # hasn't disappeared
        if uploaded_file is not None:
            st.session_state.uploaded_file = uploaded_file
            logger.info("Reading uploaded config file")
            st.session_state.config_data = json.load(st.session_state.uploaded_file)

        if run_sim:
            run_sim = False
            logger.info("Running simulation")
            st.spinner("Running simulation")
            clearing_prices_dict, all_trades_dict, all_extra_costs_dict = run_trading_simulations(st.session_state.
                                                                                                  config_data,
                                                                                                  mock_datas_path,
                                                                                                  results_path)
            st.success('Simulation finished!')

    elif page_selected == app_constants.LOAD_PAGE:
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

    elif page_selected == app_constants.BIDS_PAGE:
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
