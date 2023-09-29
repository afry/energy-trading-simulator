import logging

import pandas as pd

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import app_constants, footer
from tradingplatformpoc.app.app_comparison import convert_to_altair_df
from tradingplatformpoc.app.app_visualizations import altair_period_chart, \
    construct_agent_comparison_chart, construct_price_chart
from tradingplatformpoc.market.bid import Resource
from tradingplatformpoc.market.trade import TradeMetadataKey
from tradingplatformpoc.sql.agent.crud import get_agent_type
from tradingplatformpoc.sql.clearing_price.crud import db_to_construct_local_prices_df
from tradingplatformpoc.sql.config.crud import get_all_agents_in_config, get_all_finished_job_config_id_pairs_in_db
from tradingplatformpoc.sql.level.crud import db_to_viewable_level_df_by_agent
from tradingplatformpoc.sql.trade.crud import get_import_export_df

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()

ids = get_all_finished_job_config_id_pairs_in_db()
if len(ids) >= 2:
    first_col, second_col = st.columns(2)
    with first_col:
        chosen_config_id_to_view_1 = st.selectbox('Choose a first configuration to compare', ids.keys())
        if chosen_config_id_to_view_1 is not None:
            st.session_state.chosen_config_id_to_view_1 = {'config_id': chosen_config_id_to_view_1,
                                                           'job_id': ids[chosen_config_id_to_view_1]}
    with second_col:
        chosen_config_id_to_view_2 = st.selectbox(
            'Choose a second configuration to compare',
            [key for key in ids.keys() if key != st.session_state.chosen_config_id_to_view_1['config_id']])
        if chosen_config_id_to_view_2 is not None:
            st.session_state.chosen_config_id_to_view_2 = {'config_id': chosen_config_id_to_view_2,
                                                           'job_id': ids[chosen_config_id_to_view_2]}
            
    if ('chosen_config_id_to_view_1' in st.session_state.keys()) \
       and ('chosen_config_id_to_view_2' in st.session_state.keys()):
        # Price graph
        logger.info("Constructing price graph")
        st.spinner("Constructing price graph")

        local_price_df_1 = db_to_construct_local_prices_df(
            job_id=st.session_state.chosen_config_id_to_view_1['job_id'])
        local_price_df_1['variable'] = app_constants.LOCAL_PRICE_STR \
            + ' ' + st.session_state.chosen_config_id_to_view_1['config_id']
        local_price_df_2 = db_to_construct_local_prices_df(
            job_id=st.session_state.chosen_config_id_to_view_2['job_id'])
        local_price_df_2['variable'] = app_constants.LOCAL_PRICE_STR \
            + ' ' + st.session_state.chosen_config_id_to_view_2['config_id']
        combined_price_df = pd.concat([local_price_df_1, local_price_df_2])
        price_chart = construct_price_chart(
            combined_price_df,
            Resource.ELECTRICITY,
            [app_constants.LOCAL_PRICE_STR + ' ' + st.session_state.chosen_config_id_to_view_1['config_id'],
             app_constants.LOCAL_PRICE_STR + ' ' + st.session_state.chosen_config_id_to_view_2['config_id']],
            ['blue', 'green'],
            [[0, 0], [2, 4]])
        st.caption("Click on a variable in legend to highlight it in the graph.")
        st.altair_chart(price_chart, use_container_width=True, theme=None)

        df = get_import_export_df([st.session_state.chosen_config_id_to_view_1['job_id'],
                                   st.session_state.chosen_config_id_to_view_2['job_id']])
        df, domain = convert_to_altair_df(df)
        chart = altair_period_chart(df, domain,
                                    app_constants.ALTAIR_BASE_COLORS[:len(domain)], '')
        st.altair_chart(chart, use_container_width=True, theme=None)

        st.markdown("Agent comparison graphs. Select one agent of the same type from each scenario.")
        first_col, second_col = st.columns(2)
        with first_col:
            agent_1_specs = get_all_agents_in_config(st.session_state.chosen_config_id_to_view_1['config_id'])
            agent_1_names = [name for name in agent_1_specs.keys()]
            chosen_agent_name_to_view_1 = st.selectbox('Select an agent from the first configuration',
                                                       agent_1_names)
            agent_1_type = get_agent_type(agent_1_specs.get(chosen_agent_name_to_view_1))
        with second_col:
            agent_2_specs = get_all_agents_in_config(st.session_state.chosen_config_id_to_view_2['config_id'])
            agent_2_names = [name for name, id in agent_2_specs.items()
                             if get_agent_type(id) == agent_1_type]
            chosen_agent_name_to_view_2 = st.selectbox('Select an agent from the second configuration',
                                                       agent_2_names)
        st.markdown(f"Creating a {agent_1_type} graph")

        if not agent_2_names:
            st.markdown("There is no relevant agent in the second configuration")
        else:

            if agent_1_type == "BuildingAgent":
                # Make a heat pump workload comparison graph
                heat_pump_levels_agent_1_df = db_to_viewable_level_df_by_agent(
                    job_id=st.session_state.chosen_config_id_to_view_1['job_id'],
                    agent_guid=chosen_agent_name_to_view_1,
                    level_type=TradeMetadataKey.HEAT_PUMP_WORKLOAD.name). \
                    assign(variable=chosen_agent_name_to_view_1 + " Scenario 1")
                heat_pump_levels_agent_2_df = db_to_viewable_level_df_by_agent(
                    job_id=st.session_state.chosen_config_id_to_view_2['job_id'],
                    agent_guid=chosen_agent_name_to_view_2,
                    level_type=TradeMetadataKey.HEAT_PUMP_WORKLOAD.name). \
                    assign(variable=chosen_agent_name_to_view_2 + " Scenario 2")

                combined_heat_df = pd.concat([heat_pump_levels_agent_1_df, heat_pump_levels_agent_2_df],
                                             axis=0, join="outer").reset_index()
                heat_pump_chart = construct_agent_comparison_chart(combined_heat_df,
                                                                   title="Heat Pump Comparison",
                                                                   ylabel='Heat pump workload')
                st.altair_chart(heat_pump_chart, use_container_width=True, theme=None)

            if agent_1_type == "BatteryAgent":
                # make a battery storage level comparison graph
                storage_levels_agent_1_df = db_to_viewable_level_df_by_agent(
                    job_id=st.session_state.chosen_config_id_to_view_1['job_id'],
                    agent_guid=chosen_agent_name_to_view_1,
                    level_type=TradeMetadataKey.STORAGE_LEVEL.name). \
                    assign(variable=chosen_agent_name_to_view_1 + " Scenario 1")
                storage_levels_agent_2_df = db_to_viewable_level_df_by_agent(
                    job_id=st.session_state.chosen_config_id_to_view_2['job_id'],
                    agent_guid=chosen_agent_name_to_view_2,
                    level_type=TradeMetadataKey.STORAGE_LEVEL.name). \
                    assign(variable=chosen_agent_name_to_view_2 + " Scenario 2")
                
                combined_battery_df = pd.concat([storage_levels_agent_1_df, storage_levels_agent_2_df],
                                                axis=0, join="outer").reset_index()
                battery_chart = construct_agent_comparison_chart(combined_battery_df,
                                                                 title="Battery Storage Comparison",
                                                                 ylabel="Charge Level")
                st.altair_chart(battery_chart, use_container_width=True, theme=None)

else:
    st.markdown('Too few scenarios to compare, set up a configuration in '
                '**Setup simulation** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
