import logging
import time

import pandas as pd

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_functions import run_next_job_in_queue, set_max_width
from tradingplatformpoc.app.app_threading import get_running_threads
from tradingplatformpoc.app.app_visualizations import color_in
from tradingplatformpoc.sql.config.crud import \
    get_all_config_ids_in_db_with_jobs_df, get_all_config_ids_in_db_without_jobs, read_config
from tradingplatformpoc.sql.job.crud import create_job_if_new_config, delete_job

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()

set_max_width('1000px')  # This tab looks a bit daft when it is too wide, so limiting it here.

if len([thread for thread in get_running_threads() if 'run_' in thread.name]) == 0:
    run_started = run_next_job_in_queue()
    if run_started:
        time.sleep(5)
        st.experimental_rerun()

config_ids = get_all_config_ids_in_db_without_jobs()
chosen_config_id = st.selectbox('Choose a configuration to run', config_ids)
if len(config_ids) > 0:
    with st.expander('Configuration *{}* in JSON format'.format(chosen_config_id)):
        st.json(read_config(chosen_config_id), expanded=True)
else:
    st.markdown('Set up a configuration in **Setup simulation**')

run_sim = st.button("**CLICK TO RUN/QUEUE SIMULATION FOR *{}***".format(chosen_config_id)
                    if chosen_config_id is not None else "**CLICK TO RUN SIMULATION**",
                    disabled=(len(config_ids) == 0),
                    help='Click this button to start a simulation '
                    'run with the specified configuration: *{}*'.format(chosen_config_id),
                    type='primary')

if run_sim:
    new_job_id = create_job_if_new_config(chosen_config_id)
    run_sim = False
    st.experimental_rerun()


st.subheader('Jobs')
st.caption('Reload page in order to see latest information.')
config_df = get_all_config_ids_in_db_with_jobs_df()
if not config_df.empty:
    config_df['Delete'] = False
    # config_df['Delete'] = config_df['Delete'].astype(bool)
    config_df['Status'] = 'Could not finish'
    config_df.loc[config_df['Job ID'].isin([thread.name[4:] for thread in get_running_threads()]),
                  'Status'] = 'Running'
    config_df.loc[(config_df['Start time'].isna() & config_df['End time'].isna()), 'Status'] = 'Pending'
    config_df.loc[config_df['End time'].notna(), 'Status'] = 'Completed'
    config_df['Status'] = pd.Categorical(config_df['Status'],
                                         categories=["Running", "Pending", "Completed", "Could not finish"],
                                         ordered=True)
    config_df.sort_values('Status', inplace=True)
    config_df_styled = config_df.style.applymap(color_in, subset=['Status'])\
        .set_properties(**{'background-color': '#f5f5f5'}, subset=['Status', 'Config ID'])
    delete_runs_form = st.form(key='Delete runs form')
    edited_df = delete_runs_form.data_editor(
        config_df_styled,
        # use_container_width=True,  # Caused shaking before
        key='delete_df',
        column_config={
            "Delete": st.column_config.CheckboxColumn(
                "Delete",
                help="Check the box if you want to delete the data for this run.",
                default=False,
            )
        },
        column_order=['Status', 'Config ID', 'Delete', 'Start time', 'End time', 'Description', 'Job ID'],
        hide_index=True,
        disabled=['Status', 'Config ID', 'Start time', 'End time', 'Description', 'Job ID']
    )
    delete_runs_submit = delete_runs_form.form_submit_button('**DELETE DATA FOR SELECTED RUNS**',
                                                             help='IMPORTANT: Clicking this button '
                                                             'will delete selected jobs and all associated data.')
    if delete_runs_submit:
        delete_runs_submit = False
        if not edited_df[edited_df['Delete']].empty:
            for _i, row in edited_df[edited_df['Delete']].iterrows():
                active = [thread for thread in get_running_threads() if thread.name == 'run_' + row['Job ID']]
                if len(active) == 0:
                    delete_job(row['Job ID'])
                else:
                    active[0].stop_it()
            st.experimental_rerun()
        else:
            st.markdown('No runs selected to delete.')
else:
    st.dataframe(pd.DataFrame(columns=['Status', 'Config ID', 'Start time', 'End time', 'Description', 'Job ID']),
                 hide_index=True, use_container_width=True)

st.write(footer.html, unsafe_allow_html=True)

time.sleep(5)
st.experimental_rerun()
