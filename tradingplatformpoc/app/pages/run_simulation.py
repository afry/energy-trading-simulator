import logging

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_functions import results_button, set_max_width, set_simulation_results
from tradingplatformpoc.constants import MOCK_DATA_PATH
from tradingplatformpoc.simulation_runner.trading_simulator import TradingSimulator
from tradingplatformpoc.sql.config.crud import get_all_config_ids_in_db_with_jobs, \
    get_all_config_ids_in_db_without_jobs, read_config

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()

set_max_width('1000px')  # This tab looks a bit daft when it is too wide, so limiting it here.

config_ids = get_all_config_ids_in_db_without_jobs()
choosen_config_id = st.selectbox('Choose a configurationt to run', config_ids)
if len(config_ids) > 0:
    with st.expander('Configuration :blue[{}] in JSON format'.format(choosen_config_id)):
        st.json(read_config(choosen_config_id), expanded=True)
else:
    st.markdown('Set up a configuration in **Setup simulation**')

run_sim = st.button("Click to run simulation", disabled=(len(config_ids) == 0))
progress_bar = st.progress(0.0)
progress_text = st.info("")

st.markdown('Scenarios already run')
config_df = get_all_config_ids_in_db_with_jobs()
st.dataframe(config_df)

if not ('simulation_results' in st.session_state):
    st.caption('Be aware that the download button returns last saved simulation '
               'result which might be from another session.')

results_download_button = st.empty()
results_button(results_download_button)

if run_sim:
    run_sim = False
    logger.info("Running simulation")
    st.spinner("Running simulation")

    simulator = TradingSimulator(choosen_config_id, MOCK_DATA_PATH)
    simulation_results = simulator(progress_bar, progress_text)
    if simulation_results is not None:
        set_simulation_results(simulation_results)
        st.session_state.simulation_results = simulation_results
        logger.info("Simulation finished!")
        progress_text.success('Simulation finished!')
        results_button(results_download_button)
    else:
        progress_text.error("Simulation could not finish!")
        # TODO: Delete job ID

st.write(footer.html, unsafe_allow_html=True)
