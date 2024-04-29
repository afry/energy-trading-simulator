from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_charts import construct_agent_energy_chart, construct_bites_chart, \
    construct_storage_level_chart, construct_traded_amount_by_agent_chart
from tradingplatformpoc.app.app_constants import AGGREGATION_LEVELS
from tradingplatformpoc.app.app_data_display import build_heat_pump_prod_df, get_bites_dfs, get_storage_dfs, \
    reconstruct_static_digital_twin
from tradingplatformpoc.app.app_functions import IdPair, calculate_max_table_height, download_df_as_csv_button, \
    make_room_for_menu_in_sidebar
from tradingplatformpoc.sql.agent.crud import get_agent_config, get_agent_type
from tradingplatformpoc.sql.config.crud import get_all_agent_name_id_pairs_in_config, \
    get_all_finished_job_config_id_pairs_in_db, read_config
from tradingplatformpoc.sql.extra_cost.crud import db_to_viewable_extra_costs_df_by_agent
from tradingplatformpoc.sql.trade.crud import db_to_viewable_trade_df_by_agent

TABLE_HEIGHT: int = 300

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()
make_room_for_menu_in_sidebar()

ids = get_all_finished_job_config_id_pairs_in_db()
if len(ids) > 0:
    chosen_config_id_to_view = st.selectbox('Choose a configuration to view results for', ids.keys())
    chosen_id_to_view = IdPair(chosen_config_id_to_view, ids[chosen_config_id_to_view])
    agent_specs = get_all_agent_name_id_pairs_in_config(chosen_id_to_view.config_id)
    agent_names = [name for name in agent_specs.keys()]
    agent_chosen_guid = st.sidebar.selectbox('Choose agent:', agent_names)
    agent_type = get_agent_type(agent_specs[agent_chosen_guid])
    st.write("Showing results for: " + agent_chosen_guid)

    with st.expander('Trades'):
        trades_df = db_to_viewable_trade_df_by_agent(job_id=chosen_id_to_view.job_id,
                                                     agent_guid=agent_chosen_guid)
        if trades_df.empty:
            st.dataframe(trades_df, hide_index=True)
        else:
            height = calculate_max_table_height(len(trades_df.index))
            st.dataframe(trades_df.replace(float('inf'), 'inf'), height=height)
            download_df_as_csv_button(trades_df, "all_trades_for_agent_" + agent_chosen_guid,
                                      include_index=True)
            aggregation_type = st.radio('Aggregation:', AGGREGATION_LEVELS, horizontal=True)
            trades_chart = construct_traded_amount_by_agent_chart(agent_chosen_guid, trades_df, aggregation_type[:1])
            st.altair_chart(trades_chart, use_container_width=True, theme=None)
            st.write("Click on a variable to highlight it.")

    with st.expander('Extra costs'):
        st.write('A negative cost means that the agent was owed money for the period, rather than owing the '
                 'money to someone else.')
        extra_costs_df = db_to_viewable_extra_costs_df_by_agent(job_id=chosen_id_to_view.job_id,
                                                                agent_guid=agent_chosen_guid)
        
        if extra_costs_df.empty:
            st.dataframe(extra_costs_df, hide_index=True)
        else:
            height = calculate_max_table_height(len(extra_costs_df.index))
            st.dataframe(extra_costs_df.replace(float('inf'), 'inf'), height=height)
            download_df_as_csv_button(extra_costs_df, "extra_costs_for_agent_" + agent_chosen_guid,
                                      include_index=True)

    if agent_type != 'GridAgent':
        storage_level_dfs = get_storage_dfs(job_id=chosen_id_to_view.job_id, agent_chosen_guid=agent_chosen_guid)
        if len(storage_level_dfs) > 0:
            with st.expander('Storage levels over time for ' + agent_chosen_guid + ':'):
                storage_chart = construct_storage_level_chart(storage_level_dfs)
                st.altair_chart(storage_chart, use_container_width=True, theme=None)

        bites_dfs = get_bites_dfs(job_id=chosen_id_to_view.job_id, agent_chosen_guid=agent_chosen_guid)
        if len(bites_dfs) > 0:
            with st.expander('Building inertia thermal energy storage over time for ' + agent_chosen_guid + ':'):
                bites_chart = construct_bites_chart(bites_dfs)
                st.altair_chart(bites_chart, use_container_width=True, theme=None)

        with st.expander('Energy production/consumption'):
            agent_config = get_agent_config(agent_specs[agent_chosen_guid])
            st.caption("Click on a variable to highlight it.")

            heat_pump_prod_df = build_heat_pump_prod_df(chosen_id_to_view.job_id, agent_chosen_guid, agent_config)
            config = read_config(chosen_id_to_view.config_id)
            digital_twin = reconstruct_static_digital_twin(
                agent_specs[agent_chosen_guid], config, agent_config, agent_type)
            agent_energy_prod_cons_chart = construct_agent_energy_chart(
                digital_twin, agent_chosen_guid, heat_pump_prod_df)
            st.caption("Heat consumption here refers to the block agent's heat demand, and does not consider "
                       "the source of the heat. To investigate the effects of running heat pumps, this graph "
                       "should be studied together with the graph displaying resources bought and sold further "
                       "up the page under the *Trades*-expander.")
            st.caption("'HP high heat production' represents the production of 'normal' heat pumps in winter mode, "
                       "and 'booster' heat pumps in summer mode. 'HP low heat production' represents the production"
                       " of 'normal' heat pumps in summer mode, and is always 0 in winter mode.")

            st.altair_chart(agent_energy_prod_cons_chart, use_container_width=True, theme=None)

else:
    st.markdown('No results to view yet, set up a configuration in '
                '**Setup configuration** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
