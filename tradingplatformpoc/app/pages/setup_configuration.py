import json
import logging
from time import sleep

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import app_constants, footer
from tradingplatformpoc.app.app_functions import cleanup_config_description, cleanup_config_name, \
    config_naming_is_valid, set_max_width, update_multiselect_style
from tradingplatformpoc.app.app_inputs import add_battery_agent, add_building_agent, add_grocery_store_agent, \
    add_params_to_form, add_pv_agent, agent_inputs, duplicate_agent, remove_agent, remove_all_building_agents
from tradingplatformpoc.config.access_config import fill_agents_with_defaults, fill_with_default_params, \
    read_param_specs
from tradingplatformpoc.config.screen_config import compare_pv_efficiency, config_data_json_screening, \
    display_diff_in_config
from tradingplatformpoc.sql.config.crud import create_config_if_not_in_db, delete_config_if_no_jobs_exist, \
    get_all_config_ids_in_db, get_all_configs_in_db_df, read_description, update_description
from tradingplatformpoc.sql.config.crud import read_config

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages_subpages.toml")
add_indentation()

set_max_width('1000px')  # This tab looks a bit daft when it is too wide, so limiting it here.


options = ['...input parameters through UI.', '...upload configuration file.']
option_chosen = st.sidebar.selectbox('I want to...', options)

st.markdown('On this page you can create new scenario configurations to run simulations for. '
            'Start by selecting a configuration to compare against. '
            'If you click on the *set*-button below, then the *current* configuration is changed to '
            'the chosen existing configuration. '
            'This existing configuration can then be customized by changing parameters in the '
            'forms under **Create new configuration**.')

st.divider()

config_ids = get_all_config_ids_in_db()
chosen_config_id = st.selectbox('Choose an existing configuration.', config_ids)

if len(config_ids) > 0:
    with st.expander('chosen existing configuration :blue[{}]'.format(chosen_config_id)):
        st.write('**Configuration description**: ', read_description(chosen_config_id))
        st.markdown("##")
        # Button to export config to a JSON file
        st.download_button(label="Export *" + chosen_config_id + "* config to JSON",
                           data=json.dumps(read_config(chosen_config_id)),
                           file_name="trading-platform-poc-config-" + chosen_config_id + ".json",
                           mime="text/json", help="Click button below to download the " + chosen_config_id
                           + " configuration to a JSON-file.")
        st.markdown("#")
        st.json(read_config(chosen_config_id), expanded=True)

reset_config_button = st.button(label="SET CONFIGURATION TO **{}**".format(chosen_config_id),
                                help="Click here to DELETE custom configuration and reset configuration to "
                                "chosen base configuration", type='primary',
                                disabled=(option_chosen == options[1]))

if ('config_data' not in st.session_state.keys()) or reset_config_button:
    reset_config_button = False
    st.session_state.config_data = read_config(chosen_config_id)


st.divider()

st.caption("Button for deleting configuration {} from storage. Caution! This affects ALL USERS. "
           "Won't allow deletion if saved jobs exist. "
           "Jobs can be deleted on the *Run simulation*-page.".format(chosen_config_id))

delete_config_button = st.button(label="DELETE CONFIGURATION **{}**".format(chosen_config_id),
                                 help="Click here to DELETE the existing configuration. "
                                 "Only configurations with no saved jobs can be deleted.", type='secondary',
                                 disabled=(option_chosen == options[1]))
if delete_config_button:
    delete_config_button = False
    deleted = delete_config_if_no_jobs_exist(chosen_config_id)
    if deleted:
        st.success('Configuration deleted!')
    else:
        st.error('Could not delete configuration.')
    sleep(5)
    st.experimental_rerun()

st.markdown('---')
st.markdown("**Create new configuration**")

config_container = st.container()

st.markdown('#')

comp_pveff = compare_pv_efficiency(st.session_state.config_data)
if comp_pveff is not None:
    st.info(comp_pveff)
# TODO: Button for setting all PVEfficiency params to same value
# TODO: Same for Heatpump COP

if option_chosen == options[0]:
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

        with mock_data_constants_tab:
            # st.markdown("**Data simulation parameters for digital twin:**")  # ---------------
            mdc_form = st.form(key="MockDataConstantsForm")
            add_params_to_form(mdc_form, read_param_specs(['MockDataConstants']), 'MockDataConstants')
            submit_mdc_form = mdc_form.form_submit_button("Save mock data generation constants")
            if submit_mdc_form:
                submit_mdc_form = False

    # ------------------- Start agents -------------------
    with st.expander("Agents"):
        modify_agents_tab, add_agents_tab, delete_agents_tab = st.tabs(["Modify existing agents",
                                                                        "Add new agents",
                                                                        "Delete agents"])
        current_agents = st.session_state.config_data['Agents'][:]
        with modify_agents_tab:
            st.markdown('To change agent parameters, first select the agent name from the drop down list, '
                        'then fill out the following form. **Save** changes by clicking on the save button '
                        'at the bottom. Changes can be verified against the configuration under the '
                        '*Current configuration in JSON format*-expander.')
            current_agent_names = [agent['Name'] for agent in current_agents]
            chosen_agent_name = st.selectbox('Choose an agent to modify:', current_agent_names)
            chosen_agent_ind = current_agent_names.index(chosen_agent_name)
            agent = current_agents[chosen_agent_ind]
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

        with add_agents_tab:
            st.markdown('Select the type of the agent to add '
                        'from the drop down list, and modify the pre-selected parameter values. '
                        'Click on **Save** to create agent.')
            agent_type_options = ['BuildingAgent', 'GroceryStoreAgent', 'BatteryAgent', 'PVAgent']
            chosen_agent_type = st.selectbox('Add new agent of type:', options=agent_type_options)
            if chosen_agent_type == 'BuildingAgent':
                add_building_agent()
            elif chosen_agent_type == 'GroceryStoreAgent':
                add_grocery_store_agent()
            elif chosen_agent_type == 'BatteryAgent':
                add_battery_agent()
            elif chosen_agent_type == 'PVAgent':
                add_pv_agent()
            if 'agents_added' in st.session_state.keys() and st.session_state.agents_added:
                st.success("Last new agent added: '" + current_agents[-1]["Name"] + "'")
        with delete_agents_tab:
            st.markdown('To delete agents, select them by name from the drop down list and click on **Delete agents**.')
            delete_agents_form = st.form(key="DeleteAgentsForm")
            current_agents_possible_to_delete = {agent['Name']: agent for agent
                                                 in current_agents if agent['Type'] != 'GridAgent'}
            if len(current_agents_possible_to_delete) > 0:
                update_multiselect_style()
                agent_names_to_delete = delete_agents_form.multiselect("Agents to delete:",
                                                                       current_agents_possible_to_delete.keys(),
                                                                       default=current_agents_possible_to_delete.keys())
                submit_delete_agent = delete_agents_form.form_submit_button(':red[Delete agents]')
                if submit_delete_agent:
                    submit_delete_agent = False
                    for agent in [current_agents_possible_to_delete[name] for name in agent_names_to_delete]:
                        remove_agent(agent)
                    st.experimental_rerun()
            else:
                st.markdown('No agents available to delete.')

            st.button(":red[Remove all BuildingAgents]", on_click=remove_all_building_agents, use_container_width=True)

        # --------------------- End config specification for dummies ------------------------

if option_chosen == options[1]:
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
        st.info("Using configuration from uploaded file.")

with config_container:
    coljson, coltext = st.columns([2, 1])
    with coljson:
        with st.expander('Current configuration'):
            # Button to export config to a JSON file
            st.download_button(label="Export *current* config to JSON", data=json.dumps(st.session_state.config_data),
                               file_name="trading-platform-poc-config-current.json",
                               mime="text/json", help="Click button below to download the current experiment "
                               "configuration to a JSON-file, which you can later "
                               "upload to re-use this configuration without having to do over "
                               "any changes you have made so far.")
            st.markdown("#")
            st.json(st.session_state.config_data, expanded=True)
    with coltext:
        with st.expander('Configuration changes from default'):
            str_to_disp = display_diff_in_config(read_config(chosen_config_id), st.session_state.config_data)
            if len(str_to_disp) > 1:
                for s in str_to_disp:
                    st.markdown(s)

config_form = st.form(key='Save config')
config_name = config_form.text_input('Name', '', max_chars=app_constants.CONFIG_ID_MAX_LENGTH,
                                     help="Name should consist only of letters, and it can not be empty.")
description = config_form.text_input('Description', '', max_chars=app_constants.CONFIG_DESCRIPTION_MAX_LENGTH)
config_submit = config_form.form_submit_button('SAVE CONFIGURATION', type='primary')
if config_submit:
    config_submit = False
    if not config_naming_is_valid(config_name):
        st.error("Provide a valid name!")
    elif not config_naming_is_valid(description):
        st.error("Provide a valid description!")
    else:
        config_name = cleanup_config_name(config_name)
        description = cleanup_config_description(description)
        config_created = create_config_if_not_in_db(st.session_state.config_data, config_name, description)
        if config_created['created']:
            st.success(config_created['message'])
        else:
            st.warning(config_created['message'])
    sleep(10)
    st.experimental_rerun()

st.divider()

with st.expander('Edit descriptions'):
    st.caption("Here you can edit the descriptions of existing configurations. "
               "Change the contents of the description fields and click on the button below to save changes.")
    all_configs_df = get_all_configs_in_db_df()
    if not all_configs_df.empty:
        all_configs_df = all_configs_df.set_index('Config ID')
        edit_configs_form = st.form(key='Edit configs form')
        edited_df = edit_configs_form.data_editor(
            all_configs_df,
            # use_container_width=True,  # Caused shaking before
            key='edit_df',
            column_config={
                "Edit": st.column_config.TextColumn(
                    help="Save changes to descriptions.",
                )
            },
            hide_index=False,
            disabled=['Config ID']
        )
        edit_configs_submit = edit_configs_form.form_submit_button('**EDIT DESCRIPTIONS**',
                                                                   help='')
        if edit_configs_submit:
            edit_configs_submit = False
            for i, row in edited_df.iterrows():
                if row['Description'] != all_configs_df.loc[i, 'Description']:
                    if config_naming_is_valid(row['Description']):
                        update_description(i, cleanup_config_description(row['Description']))
                    else:
                        st.error("Provide a valid description!")

st.write(footer.html, unsafe_allow_html=True)
