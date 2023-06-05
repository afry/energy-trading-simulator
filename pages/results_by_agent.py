import streamlit as st
from st_pages import show_pages_from_config, add_indentation
from tradingplatformpoc.agent.building_agent import BuildingAgent
from tradingplatformpoc.agent.pv_agent import PVAgent
from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_functions import construct_building_with_heat_pump_chart, \
    construct_storage_level_chart, construct_traded_amount_by_agent_chart, display_df_and_make_downloadable, \
    get_agent, get_viewable_df, results_by_agent_as_df, results_by_agent_as_df_with_highlight

show_pages_from_config("pages_config/pages_subpages.toml")
add_indentation()

if 'simulation_results' in st.session_state:

    agent_ids = [x.guid for x in st.session_state.simulation_results.agents]
    agent_chosen_guid = st.sidebar.selectbox('Choose agent:', agent_ids)
    st.write("Showing results for: " + agent_chosen_guid)

    with st.expander('Bids'):
        bids_df = get_viewable_df(st.session_state.simulation_results.all_bids,
                                  key='source', value=agent_chosen_guid, want_index='period',
                                  cols_to_drop=['by_external'])
        display_df_and_make_downloadable(bids_df, "all_bids_for_agent_" + agent_chosen_guid)

    with st.expander('Trades'):
        trades_df = get_viewable_df(st.session_state.simulation_results.all_trades,
                                    key='source', value=agent_chosen_guid, want_index='period',
                                    cols_to_drop=['by_external'])
        display_df_and_make_downloadable(trades_df, "all_trades_for_agent" + agent_chosen_guid)
                        
        trades_chart = construct_traded_amount_by_agent_chart(agent_chosen_guid,
                                                              st.session_state.simulation_results.all_trades)
        st.altair_chart(trades_chart, use_container_width=True, theme=None)
        st.write("Click on a variable to highlight it.")

    with st.expander('Extra costs'):
        st.write('A negative cost means that the agent was owed money for the period, rather than owing the '
                 'money to someone else.')
        extra_costs_df = get_viewable_df(st.session_state.simulation_results.all_extra_costs,
                                         key='agent', value=agent_chosen_guid, want_index='period')
        display_df_and_make_downloadable(extra_costs_df, "extra_costs_for_agent" + agent_chosen_guid)

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
                                                               simulation_results.heat_pump_levels_dict,
                                                               agent_chosen_guid)
            st.altair_chart(hp_chart, use_container_width=True, theme=None)

    st.subheader('Aggregated results')

    results_by_agent_df = results_by_agent_as_df()
    results_by_agent_df_styled = results_by_agent_as_df_with_highlight(results_by_agent_df, agent_chosen_guid)
    display_df_and_make_downloadable(results_by_agent_df, "results_by_agent_all_agents",
                                     df_styled=results_by_agent_df_styled, height=563)

else:
    st.write('Run simulations and load data first!')

st.write(footer.html, unsafe_allow_html=True)
