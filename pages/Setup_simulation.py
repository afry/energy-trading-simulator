import json
import logging
import pickle
from app import DEFAULT_CONFIG, MOCK_DATA_PATH
from tradingplatformpoc.app import app_constants
from tradingplatformpoc.app.app_functions import add_building_agent, add_grocery_store_agent, add_params_to_form, \
    add_pv_agent, add_storage_agent, agent_inputs, config_data_json_screening, remove_all_building_agents, set_max_width

import streamlit as st
from st_pages import add_indentation

from tradingplatformpoc.simulation_runner import run_trading_simulations

logger = logging.getLogger(__name__)

add_indentation()

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
    st.session_state.config_data = DEFAULT_CONFIG

# --------------------- Start config specification for dummies ------------------------
# Could perhaps save the config to a temporary file on-change of these? That way changes won't get lost
st.write("Note: Refreshing, or closing and reopening this page, will lead to configuration changes being lost. "
         "If you wish to save your changes for another session, use the 'Export to JSON'-button below.")

st.subheader("General area parameters:")  # ---------------
area_form = st.form(key="AreaInfoForm")
add_params_to_form(area_form, 'AreaInfo')
_dummy1 = area_form.number_input(
    'CO2 penalization rate:', value=0.0, help=app_constants.CO2_PEN_RATE_HELP_TEXT, disabled=True)
area_form.form_submit_button("Save area info")

st.subheader("Constants used for generating data for digital twins:")  # ---------------
mdc_form = st.form(key="MockDataConstantsForm")
add_params_to_form(mdc_form, 'MockDataConstants')
mdc_form.form_submit_button("Save mock data generation constants")

# ------------------- Start agents -------------------
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
    st.markdown(app_constants.MOCK_DATA_CONSTANTS_MARKDOWN)
    st.json(app_constants.MOCK_DATA_CONSTANTS_EXAMPLE)
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
    uploaded_config = json.load(uploaded_file)
    try:
        check_message = config_data_json_screening(uploaded_config)
        if check_message is not None:
            st.error(check_message)
            st.error("Configuration from file not accepted.")
            raise ValueError("Bad parameters in config json.")
    except ValueError:
        st.stop()
    
    st.session_state.config_data = uploaded_config


if run_sim:
    run_sim = False
    logger.info("Running simulation")
    st.spinner("Running simulation")
    simulation_results = run_trading_simulations(st.session_state.config_data, MOCK_DATA_PATH, progress_bar,
                                                 progress_text)
    st.session_state.simulation_results = simulation_results
    logger.info("Simulation finished!")
    progress_text.success('Simulation finished!')
    results_download_button.download_button(label="Download simulation results",
                                            data=pickle.dumps(simulation_results),
                                            file_name="simulation_results.pickle",
                                            mime='application/octet-stream')
