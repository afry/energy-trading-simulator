import json
import logging
import pickle
from app import DEFAULT_CONFIG, MOCK_DATA_PATH
from tradingplatformpoc.app import app_constants
from tradingplatformpoc.app.app_functions import add_building_agent, add_grocery_store_agent, add_pv_agent,\
    add_storage_agent, agent_inputs, remove_all_building_agents, set_max_width

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
    'Electricity tax:', min_value=0.0, format='%.3f',
    value=st.session_state.config_data['AreaInfo']['ElectricityTax'],
    help=app_constants.ELECTRICITY_TAX_HELP_TEXT)

st.session_state.config_data['AreaInfo']['ElectricityGridFee'] = area_form.number_input(
    'Electricity grid fee:', min_value=0.0, format='%.3f',
    value=st.session_state.config_data['AreaInfo']['ElectricityGridFee'],
    help=app_constants.ELECTRICITY_GRID_FEE_HELP_TEXT)

st.session_state.config_data['AreaInfo']['ElectricityTaxInternal'] = area_form.number_input(
    'Electricity tax (internal):', min_value=0.0, format='%.3f',
    value=st.session_state.config_data['AreaInfo']['ElectricityTaxInternal'],
    help=app_constants.ELECTRICITY_TAX_INTERNAL_HELP_TEXT)

st.session_state.config_data['AreaInfo']['ElectricityGridFeeInternal'] = area_form.number_input(
    'Electricity grid fee (internal):', min_value=0.0, format='%.3f',
    value=st.session_state.config_data['AreaInfo']['ElectricityGridFeeInternal'],
    help=app_constants.ELECTRICITY_GRID_FEE_INTERNAL_HELP_TEXT)

st.session_state.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'] = area_form.number_input(
    'External heating wholesale price fraction:', min_value=0.0, max_value=1.0,
    value=st.session_state.config_data['AreaInfo']['ExternalHeatingWholesalePriceFraction'],
    help=app_constants.HEATING_WHOLESALE_PRICE_FRACTION_HELP_TEXT)

_dummy1 = area_form.number_input(
    'CO2 penalization rate:', value=0.0, help=app_constants.CO2_PEN_RATE_HELP_TEXT, disabled=True)

area_form.form_submit_button("Save area info")

st.subheader("Constants used for generating data for digital twins:")  # ---------------
mdc_form = st.form(key="MockDataConstantsForm")

st.session_state.config_data['MockDataConstants']['ResidentialElecKwhPerYearM2Atemp'] = mdc_form.number_input(
    'Residential electricity kWh/year/m2:', min_value=1, max_value=100,
    value=st.session_state.config_data['MockDataConstants']['ResidentialElecKwhPerYearM2Atemp'],
    help=app_constants.KWH_PER_YEAR_M2_ATEMP_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['ResidentialSpaceHeatKwhPerYearM2'] = mdc_form.number_input(
    'Residential space heat kWh/year/m2:', min_value=1, max_value=100,
    value=st.session_state.config_data['MockDataConstants']['ResidentialSpaceHeatKwhPerYearM2'],
    help=app_constants.KWH_PER_YEAR_M2_RES_SPACE_HEATING_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['ResidentialHotTapWaterKwhPerYearM2'] = mdc_form.number_input(
    'Residential hot tap water kWh/year/m2:', min_value=1, max_value=100,
    value=st.session_state.config_data['MockDataConstants']['ResidentialHotTapWaterKwhPerYearM2'],
    help=app_constants.KWH_PER_YEAR_M2_RES_HOT_TAP_WATER_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['ResidentialHeatingRelativeErrorStdDev'] = \
    mdc_form.number_input('Residential hot tap water relative standard deviation:', min_value=0.0,
                          max_value=1.0,
                          value=st.session_state.config_data['MockDataConstants']
                          ['ResidentialHeatingRelativeErrorStdDev'],
                          help=app_constants.RES_HEATING_REL_ERROR_STD_DEV_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['CommercialElecKwhPerYearM2'] = mdc_form.number_input(
    'Commercial electricity kWh/year/m2:', min_value=1, max_value=200,
    value=st.session_state.config_data['MockDataConstants']['CommercialElecKwhPerYearM2'],
    help=app_constants.COMM_ELEC_KWH_PER_YEAR_M2_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['CommercialElecRelativeErrorStdDev'] = \
    mdc_form.number_input('Commercial electricity relative standard deviation:', min_value=0.0,
                          max_value=1.0,
                          value=st.session_state.config_data['MockDataConstants']
                          ['CommercialElecRelativeErrorStdDev'],
                          help=app_constants.COMM_ELEC_REL_ERROR_STD_DEV_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['CommercialSpaceHeatKwhPerYearM2'] = mdc_form.number_input(
    'Commercial space heat kWh/year/m2:', min_value=1, max_value=100,
    value=st.session_state.config_data['MockDataConstants']['CommercialSpaceHeatKwhPerYearM2'],
    help=app_constants.KWH_SPACE_HEATING_PER_YEAR_M2_COMM_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['CommercialHotTapWaterKwhPerYearM2'] = mdc_form.number_input(
    'Commercial hot tap water kWh/year/m2:', min_value=1.0, max_value=10.0, step=0.5,
    value=st.session_state.config_data['MockDataConstants']['CommercialHotTapWaterKwhPerYearM2'],
    help=app_constants.KWH_HOT_TAP_WATER_PER_YEAR_M2_COMM_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['CommercialHotTapWaterRelativeErrorStdDev'] = \
    mdc_form.number_input('Commercial hot tap water relative standard deviation:', min_value=0.0,
                          max_value=1.0,
                          value=st.session_state.config_data['MockDataConstants']
                          ['CommercialHotTapWaterRelativeErrorStdDev'],
                          help=app_constants.COMM_HOT_TAP_WATER_REL_ERROR_STD_DEV_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['SchoolElecKwhPerYearM2'] = mdc_form.number_input(
    'School electricity kWh/year/m2:', min_value=1, max_value=200,
    value=st.session_state.config_data['MockDataConstants']['SchoolElecKwhPerYearM2'],
    help=app_constants.KWH_ELECTRICITY_PER_YEAR_M2_SCHOOL_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['SchoolElecRelativeErrorStdDev'] = \
    mdc_form.number_input('School electricity relative standard deviation:', min_value=0.0,
                          max_value=1.0,
                          value=st.session_state.config_data['MockDataConstants']
                          ['SchoolElecRelativeErrorStdDev'],
                          help=app_constants.SCHOOL_ELEC_REL_ERROR_STD_DEV_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['SchoolSpaceHeatKwhPerYearM2'] = mdc_form.number_input(
    'School space heat kWh/year/m2:', min_value=1, max_value=100,
    value=st.session_state.config_data['MockDataConstants']['SchoolSpaceHeatKwhPerYearM2'],
    help=app_constants.KWH_SPACE_HEATING_PER_YEAR_M2_SCHOOL_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['SchoolHotTapWaterKwhPerYearM2'] = mdc_form.number_input(
    'School hot tap water kWh/year/m2:', min_value=1, max_value=100,
    value=st.session_state.config_data['MockDataConstants']['SchoolHotTapWaterKwhPerYearM2'],
    help=app_constants.KWH_HOT_TAP_WATER_PER_YEAR_M2_SCHOOL_HELP_TEXT)

st.session_state.config_data['MockDataConstants']['SchoolHotTapWaterRelativeErrorStdDev'] = \
    mdc_form.number_input('School hot tap water relative standard deviation:', min_value=0.0,
                          max_value=1.0,
                          value=st.session_state.config_data['MockDataConstants']
                          ['SchoolHotTapWaterRelativeErrorStdDev'],
                          help=app_constants.SCHOOL_HOT_TAP_WATER_REL_ERROR_STD_DEV_HELP_TEXT)

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
    st.session_state.config_data = json.load(st.session_state.uploaded_file)

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
