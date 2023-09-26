import logging

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_comparison import construct_comparison_price_chart, import_export_altair_period_chart
from tradingplatformpoc.sql.config.crud import get_all_finished_job_config_id_pairs_in_db

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()

ids = get_all_finished_job_config_id_pairs_in_db()
if len(ids) >= 2:
    first_col, second_col = st.columns(2)
    with first_col:
        chosen_config_id_to_view_1 = st.selectbox('Choose a first configuration to compare', ids.keys())

    with second_col:
        chosen_config_id_to_view_2 = st.selectbox(
            'Choose a second configuration to compare',
            [key for key in ids.keys() if key != chosen_config_id_to_view_1])
            
    choosen_config_ids = [chosen_config_id_to_view_1, chosen_config_id_to_view_2]
    if None not in choosen_config_ids:
        comparison_ids = [{'config_id': cid, 'job_id': ids[cid]} for cid in choosen_config_ids]
            
        # Price graph
        logger.info("Constructing price graph")
        st.spinner("Constructing price graph")
        price_chart = construct_comparison_price_chart(comparison_ids)
        st.caption("Click on a variable in legend to highlight it in the graph.")
        st.altair_chart(price_chart, use_container_width=True, theme=None)

        # Import export graph
        logger.info("Constructing import/export graph")
        st.spinner("Constructing import/export graph")
        imp_exp_chart = import_export_altair_period_chart(comparison_ids)
        st.caption("Hold *Shift* and click on multiple variables in the legend to highlight them in the graph.")
        st.altair_chart(imp_exp_chart, use_container_width=True, theme=None)

else:
    st.markdown('Too few scenarios to compare, set up a configuration in '
                '**Setup simulation** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
