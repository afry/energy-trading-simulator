import json
import logging

from tradingplatformpoc.app import app_constants, footer
from tradingplatformpoc.app.app_functions import results_button, set_max_width, set_simulation_results

import streamlit as st
from st_pages import show_pages_from_config, add_indentation
from tradingplatformpoc.app.app_inputs import add_building_agent, add_grocery_store_agent, add_params_to_form, \
    add_pv_agent, add_storage_agent, agent_inputs, duplicate_agent, remove_agent, remove_all_building_agents
from tradingplatformpoc.config.access_config import fill_agents_with_defaults, fill_with_default_params, get_config, \
    read_config, read_param_specs, set_config
from tradingplatformpoc.config.screen_config import compare_pv_efficiency, config_data_json_screening, \
    display_diff_in_config

from tradingplatformpoc.simulation_runner import run_trading_simulations

logger = logging.getLogger(__name__)

show_pages_from_config("pages_config/pages.toml")
add_indentation()

set_max_width('1000px')  # This tab looks a bit daft when it is too wide, so limiting it here.

run_sim = st.button("Click here to run simulation")
progress_bar = st.progress(0.0)
progress_text = st.info("")

if not ('simulation_results' in st.session_state):
    st.caption('Be aware that the download button returns last saved simulation '
               'result which might be from another session.')

results_download_button = st.empty()
results_button(results_download_button)

options = ['...input parameters through UI.', '...upload configuration file.']
option_choosen = st.sidebar.selectbox('I want to...', options)

st.markdown('---')
config_container = st.container()
with config_container:
    col_config, col_reset = st.columns([4, 1])
    with col_reset:
        reset_config_button = st.button(label=":red[Reset configuration]",
                                        help="Click here to DELETE custom configuration and reset configuration"
                                        " to default values and agents.", disabled=(option_choosen == options[1]))
    with col_config:
        # Saving the config to file on-change. That way changes won't get lost
        current_config, message = get_config(reset_config_button)
        st.markdown(message)
        st.session_state.config_data = current_config
    # st.markdown('*If you wish to save your configuration for '
    #             'another session, use the **Export to JSON**-button below.*')
    # st.markdown('---')

st.markdown("**Change configuration**")

comp_pveff = compare_pv_efficiency(read_config())
if comp_pveff is not None:
    st.info(comp_pveff)
# TODO: Button for setting all PVEfficiency params to same value
# TODO: Same for Heatpump COP

if option_choosen == options[0]:
    with st.expander("General parameters"):
        st.markdown('Change parameter values by filling out the following forms. **Save** '
                    'changes by clicking on respective save button. Changes can be '
                    'verified against the configuration under the '
                    '*Current configuration in JSON format*-expander.')

        area_info_tab, mock_data_constants_tab = st.tabs(["General area parameters",
                                                          "Data simulation parameters for digital twin"])

        with area_info_tab:
            # st.markdown("**General area parameters:**")  # ---------------
            area_form = st.form(key="AreaInfoForm")
            add_params_to_form(area_form, read_param_specs(['AreaInfo']), 'AreaInfo')
            _dummy1 = area_form.number_input(
                'CO2 penalization rate:', value=0.0, help=app_constants.CO2_PEN_RATE_HELP_TEXT, disabled=True)
            submit_area_form = area_form.form_submit_button("Save area info")
            if submit_area_form:
                submit_area_form = False
                set_config(st.session_state.config_data)

        with mock_data_constants_tab:
            # st.markdown("**Data simulation parameters for digital twin:**")  # ---------------
            mdc_form = st.form(key="MockDataConstantsForm")
            add_params_to_form(mdc_form, read_param_specs(['MockDataConstants']), 'MockDataConstants')
            submit_mdc_form = mdc_form.form_submit_button("Save mock data generation constants")
            if submit_mdc_form:
                submit_mdc_form = False
                set_config(st.session_state.config_data)

    # ------------------- Start agents -------------------
    with st.expander("Agents"):
        modify_agents_tab, add_agents_tab = st.tabs(["Modify existing agents",
                                                     "Add new agents"])
        current_agents = st.session_state.config_data['Agents'][:]
        with modify_agents_tab:
            st.markdown('To change agent parameters, first select the agent name from the drop down list, '
                        'then fill out the following form. **Save** changes by clicking on the save button '
                        'at the bottom. Changes can be verified against the configuration under the '
                        '*Current configuration in JSON format*-expander.')
            current_agent_names = [agent['Name'] for agent in current_agents]
            choosen_agent_name = st.selectbox('Choose an agent to modify:', current_agent_names)
            choosen_agent_ind = current_agent_names.index(choosen_agent_name)
            agent = current_agents[choosen_agent_ind]
            agent_inputs(agent)

            # Additional buttons
            col1, col2 = st.columns(2)
            with col1:
                st.button(label=':red[Remove agent]', key='RemoveButton' + agent['Name'],
                          on_click=remove_agent, args=(agent,),
                          use_container_width=True)
            with col2:
                st.button(label='Duplicate agent', key='DuplicateButton' + agent['Name'],
                          on_click=duplicate_agent, args=(agent,),
                          use_container_width=True)

            st.button(":red[Remove all BuildingAgents]", on_click=remove_all_building_agents, use_container_width=True)

        with add_agents_tab:
            st.markdown('Select the type of the agent to add '
                        'from the drop down list, and modify the pre-selected parameter values. '
                        'Clicke on **Save** to create agent.')
            agent_type_options = ['BuildingAgent', 'GroceryStoreAgent', 'StorageAgent', 'PVAgent']
            choosen_agent_type = st.selectbox('Add new agent of type:', options=agent_type_options)
            if choosen_agent_type == 'BuildingAgent':
                add_building_agent()
            elif choosen_agent_type == 'GroceryStoreAgent':
                add_grocery_store_agent()
            elif choosen_agent_type == 'StorageAgent':
                add_storage_agent()
            elif choosen_agent_type == 'PVAgent':
                add_pv_agent()
            if 'agents_added' in st.session_state.keys() and st.session_state.agents_added:
                st.success("Last new agent added: '" + current_agents[-1]["Name"] + "'")
        # --------------------- End config specification for dummies ------------------------

if option_choosen == options[1]:
    uploaded_file = st.file_uploader(label="Upload configuration", type="json",
                                     help="Expand the sections below for information on how the configuration file "
                                          "should look")
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
        uploaded_config = fill_with_default_params(uploaded_config)
        uploaded_config = fill_agents_with_defaults(uploaded_config)
        set_config(uploaded_config)
        st.info("Using configuration from uploaded file.")

st.markdown('---')
with config_container:
    coljson, coltext = st.columns([2, 1])
    with coljson:
        with st.expander('Current configuration in JSON format'):
            st.json(read_config(), expanded=True)
    with coltext:
        with st.expander('Configuration changes from default'):
            str_to_disp = display_diff_in_config(read_config(name='default'), read_config())
            if len(str_to_disp) > 1:
                for s in str_to_disp:
                    st.markdown(s)

    st.write("Click button below to download the current experiment configuration to a JSON-file, which you can later "
             "upload to re-use this configuration without having to do over any changes you have made so far.")
    # Button to export config to a JSON file
    st.download_button(label="Export to JSON", data=json.dumps(read_config()),
                       file_name="trading-platform-poc-config.json",
                       mime="text/json")
    st.markdown('---')

if run_sim:
    run_sim = False
    logger.info("Running simulation")
    st.spinner("Running simulation")
    simulation_results = run_trading_simulations(read_config(), app_constants.MOCK_DATA_PATH,
                                                 progress_bar, progress_text)
    set_simulation_results(simulation_results)
    st.session_state.simulation_results = simulation_results
    logger.info("Simulation finished!")
    progress_text.success('Simulation finished!')
    results_button(results_download_button)

st.write(footer.html, unsafe_allow_html=True)
