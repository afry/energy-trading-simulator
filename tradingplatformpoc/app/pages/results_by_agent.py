from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_functions import download_df_as_csv_button
from tradingplatformpoc.app.app_visualizations import construct_storage_level_chart, \
    construct_traded_amount_by_agent_chart, get_savings_vs_only_external_buy, get_total_profit_net
from tradingplatformpoc.market.trade import TradeMetadataKey
from tradingplatformpoc.sql.agent.crud import get_agent_type
from tradingplatformpoc.sql.bid.crud import db_to_viewable_bid_df_for_agent
from tradingplatformpoc.sql.config.crud import get_all_agents_in_config
from tradingplatformpoc.sql.extra_cost.crud import db_to_viewable_extra_costs_df_by_agent
from tradingplatformpoc.sql.level.crud import db_to_viewable_level_df_by_agent
from tradingplatformpoc.sql.trade.crud import db_to_viewable_trade_df_by_agent, \
    get_total_grid_fee_paid_on_internal_trades, get_total_tax_paid

TABLE_HEIGHT: int = 300

show_pages_from_config("tradingplatformpoc/app/pages_config/pages_subpages.toml")
add_indentation()

if 'chosen_id_to_view' in st.session_state.keys() and st.session_state.chosen_id_to_view is not None:

    agent_specs = get_all_agents_in_config(st.session_state.chosen_id_to_view['config_id'])
    agent_ids = [name for name in agent_specs.keys()]
    agent_chosen_guid = st.sidebar.selectbox('Choose agent:', agent_ids)
    st.write("Showing results for: " + agent_chosen_guid)

    with st.expander('Bids'):
        bids_df = db_to_viewable_bid_df_for_agent(job_id=st.session_state.chosen_id_to_view['job_id'],
                                                  agent_guid=agent_chosen_guid)
        if bids_df.empty:
            st.dataframe(bids_df, hide_index=True)
        else:
            st.dataframe(bids_df.replace(float('inf'), 'inf'), height=TABLE_HEIGHT)
            download_df_as_csv_button(bids_df, "all_bids_for_agent_" + agent_chosen_guid,
                                      include_index=True)

    with st.expander('Trades'):
        trades_df = db_to_viewable_trade_df_by_agent(job_id=st.session_state.chosen_id_to_view['job_id'],
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
        extra_costs_df = db_to_viewable_extra_costs_df_by_agent(job_id=st.session_state.chosen_id_to_view['job_id'],
                                                                agent_guid=agent_chosen_guid)
        
        if extra_costs_df.empty:
            st.dataframe(extra_costs_df, hide_index=True)
        else:
            st.dataframe(extra_costs_df.replace(float('inf'), 'inf'), height=TABLE_HEIGHT)
            download_df_as_csv_button(extra_costs_df, "extra_costs_for_agent_" + agent_chosen_guid,
                                      include_index=True)
    levels_df = db_to_viewable_level_df_by_agent(job_id=st.session_state.chosen_id_to_view['job_id'],
                                                 agent_guid=agent_chosen_guid,
                                                 level_type=TradeMetadataKey.STORAGE_LEVEL.name)
    if not levels_df.empty:
        with st.expander('Charging level over time for ' + agent_chosen_guid + ':'):
            storage_chart = construct_storage_level_chart(levels_df)
            st.altair_chart(storage_chart, use_container_width=True, theme=None)
    
    # Exclude GridAgent
    agent_type = get_agent_type(agent_specs[agent_chosen_guid])
    if agent_type != 'GridAgent':

        total_saved, extra_costs_for_bad_bids = get_savings_vs_only_external_buy(
            job_id=st.session_state.chosen_id_to_view['job_id'],
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
        if agent_type == 'BatteryAgent':
            battery_agent_total_net_profit = get_total_profit_net(
                job_id=st.session_state.chosen_id_to_view['job_id'],
                agent_guid=agent_chosen_guid)
            st.metric(
                label="Net profit.",
                value="{:,.2f} SEK".format(battery_agent_total_net_profit),
                help=r"What the {} sold minus what it bought.".format(agent_chosen_guid))
            battery_agent_tax_paid = get_total_tax_paid(
                job_id=st.session_state.chosen_id_to_view['job_id'],
                agent_guid=agent_chosen_guid)
            battery_agent_grid_fee_paid = get_total_grid_fee_paid_on_internal_trades(
                job_id=st.session_state.chosen_id_to_view['job_id'],
                agent_guid=agent_chosen_guid)
            st.metric(
                label="Gross profit.",
                value="{:,.2f} SEK".format(
                    battery_agent_total_net_profit + battery_agent_tax_paid + battery_agent_grid_fee_paid),
                help=r"Net profit plus what the {} paid for tax and grid fees.".format(agent_chosen_guid))


# TODO: Update graphs to work with results taken from database
# if 'simulation_results' in st.session_state:

#     agent_chosen = get_agent(st.session_state.simulation_results.agents, agent_chosen_guid)

#     if isinstance(agent_chosen, BuildingAgent) or isinstance(agent_chosen, PVAgent):
#         # Any building agent with a StaticDigitalTwin
#         with st.expander('Energy production/consumption'):
#             hp_chart = construct_building_with_heat_pump_chart(agent_chosen, st.session_state.
#                                                                simulation_results.heat_pump_levels_dict)
#             st.altair_chart(hp_chart, use_container_width=True, theme=None)
#             st.write("Click on a variable to highlight it.")

else:
    st.write("There's no results to view yet.")

st.write(footer.html, unsafe_allow_html=True)
