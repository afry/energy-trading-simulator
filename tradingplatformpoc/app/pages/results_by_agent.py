from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_charts import construct_agent_with_heat_pump_chart, \
    construct_traded_amount_by_agent_chart
from tradingplatformpoc.app.app_data_display import build_heat_pump_levels_df, \
    get_savings_vs_only_external_buy, reconstruct_static_digital_twin
from tradingplatformpoc.app.app_functions import download_df_as_csv_button, make_room_for_menu_in_sidebar
from tradingplatformpoc.sql.agent.crud import get_agent_config, get_agent_type
from tradingplatformpoc.sql.bid.crud import db_to_viewable_bid_df_for_agent
from tradingplatformpoc.sql.config.crud import get_all_agents_in_config, get_all_finished_job_config_id_pairs_in_db, \
    read_config
from tradingplatformpoc.sql.extra_cost.crud import db_to_viewable_extra_costs_df_by_agent
from tradingplatformpoc.sql.trade.crud import db_to_viewable_trade_df_by_agent

TABLE_HEIGHT: int = 300

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()
make_room_for_menu_in_sidebar()

ids = get_all_finished_job_config_id_pairs_in_db()
if len(ids) > 0:
    chosen_config_id_to_view = st.selectbox('Choose a configuration to view results for', ids.keys())
    chosen_id_to_view = {'config_id': chosen_config_id_to_view,
                         'job_id': ids[chosen_config_id_to_view]}
    agent_specs = get_all_agents_in_config(chosen_id_to_view['config_id'])
    agent_names = [name for name in agent_specs.keys()]
    agent_chosen_guid = st.sidebar.selectbox('Choose agent:', agent_names)
    agent_type = get_agent_type(agent_specs[agent_chosen_guid])
    st.write("Showing results for: " + agent_chosen_guid)

    with st.expander('Bids'):
        bids_df = db_to_viewable_bid_df_for_agent(job_id=chosen_id_to_view['job_id'],
                                                  agent_guid=agent_chosen_guid)
        if bids_df.empty:
            st.dataframe(bids_df, hide_index=True)
        else:
            st.dataframe(bids_df.replace(float('inf'), 'inf'), height=TABLE_HEIGHT)
            download_df_as_csv_button(bids_df, "all_bids_for_agent_" + agent_chosen_guid,
                                      include_index=True)

    with st.expander('Trades'):
        trades_df = db_to_viewable_trade_df_by_agent(job_id=chosen_id_to_view['job_id'],
                                                     agent_guid=agent_chosen_guid)
        if trades_df.empty:
            st.dataframe(trades_df, hide_index=True)
        else:
            st.dataframe(trades_df.replace(float('inf'), 'inf'), height=TABLE_HEIGHT)
            download_df_as_csv_button(trades_df, "all_trades_for_agent_" + agent_chosen_guid,
                                      include_index=True)
            trades_chart = construct_traded_amount_by_agent_chart(agent_chosen_guid, trades_df)
            st.altair_chart(trades_chart, use_container_width=True, theme=None)
            st.write("Click on a variable to highlight it.")

    with st.expander('Extra costs'):
        st.write('A negative cost means that the agent was owed money for the period, rather than owing the '
                 'money to someone else.')
        extra_costs_df = db_to_viewable_extra_costs_df_by_agent(job_id=chosen_id_to_view['job_id'],
                                                                agent_guid=agent_chosen_guid)
        
        if extra_costs_df.empty:
            st.dataframe(extra_costs_df, hide_index=True)
        else:
            st.dataframe(extra_costs_df.replace(float('inf'), 'inf'), height=TABLE_HEIGHT)
            download_df_as_csv_button(extra_costs_df, "extra_costs_for_agent_" + agent_chosen_guid,
                                      include_index=True)

    # TODO: uncomment when we've fixed saving storage level for block agents
    # if agent_type == 'BlockAgent':
    #     storage_levels_df = db_to_viewable_level_df_by_agent(job_id=chosen_id_to_view['job_id'],
    #                                                          agent_guid=agent_chosen_guid,
    #                                                          level_type=TradeMetadataKey.STORAGE_LEVEL.name)
    #     if not storage_levels_df.empty:
    #         with st.expander('Charging level over time for ' + agent_chosen_guid + ':'):
    #             storage_chart = construct_storage_level_chart(storage_levels_df)
    #             st.altair_chart(storage_chart, use_container_width=True, theme=None)
    
    # Exclude GridAgent
    if agent_type != 'GridAgent':

        total_saved, extra_costs_for_bad_bids = get_savings_vs_only_external_buy(
            job_id=chosen_id_to_view['job_id'],
            agent_guid=agent_chosen_guid)

        st.metric(
            label="Savings from using the local market before taking penalties into account.",
            value="{:,.2f} SEK".format(total_saved),
            help="Amount saved for agent {} by using local market, ".format(agent_chosen_guid)
            + r"as opposed to only using the external grid. "
            r"The value is the sum of savings on buy trades where the buyer pays for "
            r"the quantity before losses:"
            r"$\sum \limits_{\text{buy}}$ quantity $ \cdot$ (retail price $-$ price)"
            r" and savings on sell trades, where the seller is payed for the quantity after losses: "
            r"$\sum \limits_\text{sell}$ (quantity $-$ loss) $\cdot$ (price $-$ wholesale price)"
            r" minus heat cost corrections.")

        st.metric(
            label="Total penalties accrued for bid inaccuracies.",
            value="{:,.2f} SEK".format(extra_costs_for_bad_bids),
            help=r"Agent {} was penalized with a total of {:,.2f} SEK due to inaccurate projections. This brought "
                 r"total savings after penalties to {:,.2f} SEK.".format(agent_chosen_guid, extra_costs_for_bad_bids,
                                                                         total_saved - extra_costs_for_bad_bids))

    if agent_type == "BlockAgent":
        with st.expander('Energy production/consumption'):
            agent_config = get_agent_config(agent_specs[agent_chosen_guid])
            st.caption("Click on a variable to highlight it.")
            if agent_type == 'BlockAgent':
                heat_pump_levels_df = build_heat_pump_levels_df(agent_chosen_guid, chosen_id_to_view['job_id'],
                                                                agent_config)
                config = read_config(chosen_id_to_view['config_id'])
                block_digital_twin = reconstruct_static_digital_twin(
                    agent_specs[agent_chosen_guid], config['MockDataConstants'],
                    agent_config['PVArea'], config['AreaInfo']['PVEfficiency'])
                static_digital_twin_chart = construct_agent_with_heat_pump_chart(
                    agent_chosen_guid, block_digital_twin, heat_pump_levels_df)
                st.caption("Heat consumption here refers to the block agent's heat demand, and does not consider "
                           "the source of the heat. To investigate the effects of running heat pumps, this graph "
                           "should be studied together with the graph displaying resources bought and sold further "
                           "up the page under the *Trades*-expander.")

            st.altair_chart(static_digital_twin_chart, use_container_width=True, theme=None)

else:
    st.markdown('No results to view yet, set up a configuration in '
                '**Setup simulation** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
