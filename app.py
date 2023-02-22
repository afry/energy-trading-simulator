import os
import pickle
from logging.handlers import TimedRotatingFileHandler

from pkg_resources import resource_filename

from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.app import app_constants, footer
from tradingplatformpoc.app.app_functions import add_building_agent, add_grocery_store_agent, agent_inputs, \
    add_pv_agent, add_storage_agent, aggregated_import_and_export_results_df, \
    aggregated_import_and_export_results_df_split_on_period, \
    aggregated_import_and_export_results_df_split_on_temperature, \
    aggregated_taxes_and_fees_results_df, construct_building_with_heat_pump_chart, construct_price_chart, \
    construct_prices_df, construct_storage_level_chart, get_agent, get_price_df_when_local_price_inbetween, \
    get_viewable_df, results_dict_to_df, remove_all_building_agents, set_max_width
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

# --- Define path to mock data and results
mock_datas_path = resource_filename("tradingplatformpoc.data", "mock_datas.pickle")
config_filename = resource_filename("tradingplatformpoc.data", "default_config.json")
with open(config_filename, "r") as jsonfile:
    default_config = json.load(jsonfile)

if string_to_log_later is not None:
    logger.info(string_to_log_later)


if __name__ == '__main__':

    st.set_page_config(page_title="Trading platform POC", layout="wide")

    st.sidebar.write("""
    # Navigation
    """)

    page_selected = st.sidebar.radio(app_constants.SELECT_PAGE_RADIO_LABEL, app_constants.ALL_PAGES)

    if page_selected == app_constants.START_PAGE:
        st.write(
            """
            # Prototype data presentation app for energy microgrid trading platform

            Here, you can upload, select and run simulations, and evaluate the results with tables and graphs.
            """
        )
    elif page_selected == app_constants.SETUP_PAGE:
        set_max_width('1000px')  # This tab looks a bit daft when it is too wide, so limiting it here.

        run_sim = st.button("Click here to run simulation")
        progress_bar = st.progress(0.0)
        progress_text = st.info("")
        results_download_button = st.empty()
        if "simulation_results" in st.session_state:
            results_download_button.download_button(label="Download simulation results",
                                                    data=pickle.dumps(st.session_state.simulation_results),
                                                    file_name="simulation_results.pickle",
                                                    mime='application/octet-stream')
        else:
            results_download_button.download_button(label="Download simulation results", data=b'placeholder',
                                                    disabled=True)

        if ("config_data" not in st.session_state.keys()) or (st.session_state.config_data is None):
            logger.debug("Using default configuration")
            st.session_state.config_data = default_config

        # --------------------- Start config specification for dummies ------------------------
        # Could perhaps save the config to a temporary file on-change of these? That way changes won't get lost
        st.write("Note: Refreshing, or closing and reopening this page, will lead to configuration changes being lost. "
                 "If you wish to save your changes for another session, use the 'Export to JSON'-button below.")
        st.subheader("General area parameters:")
        area_form = st.form(key="AreaInfoForm")
        st.session_state.config_data['AreaInfo']['DefaultPVEfficiency'] = area_form.number_input(
            'Default PV efficiency:', min_value=0.01, max_value=0.99, format='%.3f',
            value=st.session_state.config_data['AreaInfo']['DefaultPVEfficiency'],
            help=app_constants.DEFAULT_PV_EFFICIENCY_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['HeatTransferLoss'] = area_form.number_input(
            'Heat transfer loss:', min_value=0.0, max_value=0.99, format='%.3f',
            value=st.session_state.config_data['AreaInfo']['HeatTransferLoss'],
            help=app_constants.HEAT_TRANSFER_LOSS_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ExternalElectricityWholesalePriceOffset'] = area_form.number_input(
            'External electricity wholesale price offset:', min_value=-1.0, max_value=1.0,
            value=st.session_state.config_data['AreaInfo']['ExternalElectricityWholesalePriceOffset'],
            help=app_constants.ELECTRICITY_WHOLESALE_PRICE_OFFSET_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ElectricityTax'] = area_form.number_input(
            'Electricity tax:', min_value=0.0,
            value=st.session_state.config_data['AreaInfo']['ElectricityTax'],
            help=app_constants.ELECTRICITY_TAX_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ElectricityGridFee'] = area_form.number_input(
            'Electricity grid fee:', min_value=0.0,
            value=st.session_state.config_data['AreaInfo']['ElectricityGridFee'],
            help=app_constants.ELECTRICITY_GRID_FEE_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ElectricityTaxInternal'] = area_form.number_input(
            'Electricity tax (internal):', min_value=0.0,
            value=st.session_state.config_data['AreaInfo']['ElectricityTaxInternal'],
            help=app_constants.ELEC_TAX_INTERNAL_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ElectricityGridFeeInternal'] = area_form.number_input(
            'Electricity grid fee (internal):', min_value=0.0,
            value=st.session_state.config_data['AreaInfo']['ElectricityGridFeeInternal'],
            help=app_constants.ELEC_GRID_FEE_INTERNAL_HELP_TEXT)

        st.session_state.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'] = area_form.number_input(
            'External heating wholesale price fraction:', min_value=0.0, max_value=1.0,
            value=st.session_state.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'],
            help=app_constants.HEATING_WHOLESALE_PRICE_FRACTION_HELP_TEXT)

        _dummy1 = area_form.number_input(
            'CO2 penalization rate:', value=0.0, help=app_constants.CO2_PEN_RATE_HELP_TEXT, disabled=True)

        area_form.form_submit_button("Save area info")

        # Start agents
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Agents:")
        with col2:
            st.button("Remove all BuildingAgents", on_click=remove_all_building_agents)

        for agent in st.session_state.config_data['Agents'][:]:
            # Annoyingly, this expander's name doesn't update right away when the agent's name is changed
            with st.expander(agent['Name']):
                agent_inputs(agent)
        # Buttons to add agents
        col1, col2 = st.columns(2)

        # Annoyingly, these buttons have different sizes depending on the amount of text in them.
        # Can use CSS to customize buttons but that then applies to all buttons on the page, so will leave as is
        with col1:
            add_building_agent_button = st.button("Add BuildingAgent", on_click=add_building_agent)
            add_grocery_store_agent_button = st.button("Add GroceryStoreAgent", on_click=add_grocery_store_agent)
        with col2:
            add_storage_agent_button = st.button("Add StorageAgent", on_click=add_storage_agent)
            add_pv_agent_button = st.button("Add PVAgent", on_click=add_pv_agent)

        st.write("Click below to download the current experiment configuration to a JSON-file, which you can later "
                 "upload to re-use this configuration without having to do over any changes you have made so far.")
        # Button to export config to a JSON file
        st.download_button(label="Export to JSON", data=json.dumps(st.session_state.config_data),
                           file_name="trading-platform-poc-config.json",
                           mime="text/json")

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
            simulation_results = run_trading_simulations(st.session_state.config_data, mock_datas_path, progress_bar,
                                                         progress_text)
            st.session_state.simulation_results = simulation_results
            logger.info("Simulation finished!")
            progress_text.success('Simulation finished!')
            results_download_button.download_button(label="Download simulation results",
                                                    data=pickle.dumps(simulation_results),
                                                    file_name="simulation_results.pickle",
                                                    mime='application/octet-stream')

    elif page_selected == app_constants.LOAD_PAGE:

        uploaded_results_file = st.file_uploader(label="Upload results", type="pickle", help="Some help-text")
        if uploaded_results_file is not None:
            st.session_state.uploaded_results_file = uploaded_results_file
            logger.info("Reading uploaded results file")
            st.session_state.simulation_results = pickle.load(uploaded_results_file)

        load_button = st.button("Click here to load data", disabled='simulation_results' not in st.session_state)

        if load_button:
            load_button = False
            
            logger.info("Constructing price graph")
            st.spinner("Constructing price graph")

            st.session_state.combined_price_df = construct_prices_df(st.session_state.simulation_results)
            price_chart = construct_price_chart(st.session_state.combined_price_df, Resource.ELECTRICITY)

            st.session_state.price_chart = price_chart

            st.success("Data loaded!")

            with st.expander('Current configuration in JSON format:'):
                st.json(body=json.dumps(st.session_state.simulation_results.config_data), expanded=False)

            # TODO: Display all this neater, and put the code away somewhere better. Perhaps st.table or st.dataframe
            with st.expander('Taxes and fees on internal trades:'):
                tax_fee = aggregated_taxes_and_fees_results_df()
                st.dataframe(tax_fee)
                st.caption("Tax paid includes taxes that the ElectricityGridAgent "
                           "are to pay, on sales to the microgrid.")

            with st.expander('Total imported and exported electricity and heating:'):
                imp_exp = aggregated_import_and_export_results_df()
                st.dataframe(imp_exp)
                
            with st.expander('Total imported and exported electricity and heating, split by period:'):
                imp_exp_period = aggregated_import_and_export_results_df_split_on_period()
                st.dataframe(imp_exp_period)

            with st.expander('Total imported and exported electricity and heating, split by temperature:'):
                imp_exp_temp = aggregated_import_and_export_results_df_split_on_temperature()
                st.dataframe(imp_exp_temp)
                st.caption("Split on temperature above or below 1 degree Celsius.")

        if 'price_chart' in st.session_state:
            st.altair_chart(st.session_state.price_chart, use_container_width=True, theme=None)
            with st.expander("Periods where local electricity price was between external retail and wholesale price:"):
                st.dataframe(get_price_df_when_local_price_inbetween(st.session_state.combined_price_df,
                                                                     Resource.ELECTRICITY))

    elif page_selected == app_constants.BIDS_PAGE:
        if 'simulation_results' in st.session_state:
            agent_ids = [x.guid for x in st.session_state.simulation_results.agents]
            agent_chosen_guid = st.selectbox(label='Choose agent', options=agent_ids)
            with st.expander('Bids'):
                st.dataframe(get_viewable_df(st.session_state.simulation_results.all_bids,
                                             key='source', value=agent_chosen_guid, want_index='period',
                                             cols_to_drop=['by_external']))
            with st.expander('Trades'):
                st.dataframe(get_viewable_df(st.session_state.simulation_results.all_trades,
                                             key='source', value=agent_chosen_guid, want_index='period',
                                             cols_to_drop=['by_external']))
            with st.expander('Extra costs'):
                st.write('A negative cost means that the agent was owed money for the period, rather than owing the '
                         'money to someone else.')
                st.dataframe(get_viewable_df(st.session_state.simulation_results.all_extra_costs,
                                             key='agent', value=agent_chosen_guid, want_index='period'))

            agent_chosen = get_agent(st.session_state.simulation_results.agents, agent_chosen_guid)

            if agent_chosen_guid in st.session_state.simulation_results.storage_levels_dict:
                with st.expander('Charging level over time for ' + agent_chosen_guid + ':'):
                    storage_chart = construct_storage_level_chart(
                        st.session_state.simulation_results.storage_levels_dict[agent_chosen_guid])
                    st.altair_chart(storage_chart, use_container_width=True, theme=None)

            if isinstance(agent_chosen, BuildingAgent) or isinstance(agent_chosen, PVAgent):
                # Any building agent with a StaticDigitalTwin
                with st.expander('Energy production/consumption'):
                    hp_chart = construct_building_with_heat_pump_chart(agent_chosen, st.session_state.
                                                                       simulation_results.heat_pump_levels_dict)
                    st.altair_chart(hp_chart, use_container_width=True, theme=None)

            st.subheader('Aggregated results')
            # Table with things calculated in results_calculator
            # TODO: Perhaps show all agents (one column for each), and highlight the column for agent_chosen
            st.dataframe(data=results_dict_to_df(
                st.session_state.simulation_results.results_by_agent[agent_chosen_guid]))

        else:
            st.write('Run simulations and load data first!')

    st.write(footer.html, unsafe_allow_html=True)
