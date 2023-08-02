import logging
import threading

from st_pages import add_indentation, show_pages_from_config

import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_functions import run_simulation, set_max_width
from tradingplatformpoc.sql.config.crud import get_all_config_ids_in_db_with_jobs, \
    get_all_config_ids_in_db_without_jobs, read_config
from tradingplatformpoc.sql.job.crud import delete_job

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()

set_max_width('1000px')  # This tab looks a bit daft when it is too wide, so limiting it here.

config_ids = get_all_config_ids_in_db_without_jobs()
choosen_config_id = st.selectbox('Choose a configurationt to run', config_ids)
if len(config_ids) > 0:
    with st.expander('Configuration *{}* in JSON format'.format(choosen_config_id)):
        st.json(read_config(choosen_config_id), expanded=True)
else:
    st.markdown('Set up a configuration in **Setup simulation**')

run_sim = st.button("**CLICK TO RUN SIMULATION FOR *{}***".format(choosen_config_id)
                    if choosen_config_id is not None else "**CLICK TO RUN SIMULATION**",
                    disabled=(len(config_ids) == 0),
                    help='Click this button to start a simulation '
                    'run with the specified configuration: *{}*'.format(choosen_config_id),
                    type='primary')

st.subheader('Jobs')
config_df = get_all_config_ids_in_db_with_jobs()
if not config_df.empty:
    config_df['Delete'] = False
    delete_runs_form = st.form(key='Delete runs form')
    edited_df = delete_runs_form.data_editor(
        config_df.set_index('Job ID'),
        # use_container_width=True, # Caused shaking
        key='delete_df',
        column_config={
            "Delete": st.column_config.CheckboxColumn(
                "Delete",
                help="Check the box if you want to delete the data for this run.",
                default=False,
            )
        },
        hide_index=True,
        disabled=["widgets"]
    )
    delete_runs_submit = delete_runs_form.form_submit_button('**DELETE DATA FOR SELECTED RUNS**',
                                                             help='IMPORTANT: Clicking this button '
                                                             'will delete selected jobs and all associated data.')
    if delete_runs_submit:
        delete_runs_submit = False
        if not edited_df[edited_df['Delete']].empty:
            for job_id, _row in edited_df[edited_df['Delete']].iterrows():
                delete_job(job_id)
            st.experimental_rerun()
        else:
            st.markdown('No runs selected to delete.')

if run_sim:
    t = threading.Thread(name='run_' + choosen_config_id, target=run_simulation, args=(choosen_config_id,))
    add_script_run_ctx(t)
    t.start()
    run_sim = False
    st.experimental_rerun()

# TODO: Add functionality to schedule removal of potential uncompleted jobs

# Display currently running jobs
currently_running = [thread.name[4:] for thread in threading.enumerate()
                     if (('run_' in thread.name) and (thread.is_alive()))]
if len(currently_running) > 0:
    st.markdown('Active jobs:')
    for active_cid in currently_running:
        st.info("Running job for config: {}".format(active_cid))

st.write(footer.html, unsafe_allow_html=True)
