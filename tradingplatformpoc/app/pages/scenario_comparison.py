import logging

import pandas as pd

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_comparison import construct_comparison_price_chart, import_export_altair_period_chart
from tradingplatformpoc.app.app_visualizations import construct_agent_comparison_chart
from tradingplatformpoc.market.trade import TradeMetadataKey
from tradingplatformpoc.sql.agent.crud import get_agent_type
from tradingplatformpoc.sql.config.crud import get_all_agents_in_config, get_all_finished_job_config_id_pairs_in_db
from tradingplatformpoc.sql.level.crud import db_to_viewable_level_df_by_agent
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

        # Agent comparison
        st.markdown("Agent comparison graphs. Select one agent of the same type from each scenario.")
        first_col, second_col = st.columns(2)
        with first_col:
            agent_1_specs = get_all_agents_in_config(comparison_ids[0]['config_id'])
            agent_1_names = [name for name, id in agent_1_specs.items()
                             if get_agent_type(id) in ["BuildingAgent", "BatteryAgent"]]
            chosen_agent_name_to_view_1 = st.selectbox('Select an agent from the first configuration',
                                                       agent_1_names)
            agent_1_type = get_agent_type(agent_1_specs.get(chosen_agent_name_to_view_1))
        with second_col:
            agent_2_specs = get_all_agents_in_config(comparison_ids[1]['config_id'])
            agent_2_names = [name for name, id in agent_2_specs.items()
                             if get_agent_type(id) == agent_1_type]
            chosen_agent_name_to_view_2 = st.selectbox('Select an agent from the second configuration',
                                                       agent_2_names)
        st.markdown(f"Creating a {agent_1_type} graph")

        if not agent_2_names:
            st.markdown("There is no relevant agent in the second configuration")
        else:
            if agent_1_type == "BuildingAgent":
                N = 10
                # Make a heat pump workload comparison graph
                heat_pump_levels_agent_1_df = db_to_viewable_level_df_by_agent(
                    job_id=comparison_ids[0]['job_id'],
                    agent_guid=chosen_agent_name_to_view_1,
                    level_type=TradeMetadataKey.HEAT_PUMP_WORKLOAD.name). \
                    assign(variable=chosen_agent_name_to_view_1[:N] + "... Scenario 1")
                heat_pump_levels_agent_2_df = db_to_viewable_level_df_by_agent(
                    job_id=comparison_ids[1]['job_id'],
                    agent_guid=chosen_agent_name_to_view_2,
                    level_type=TradeMetadataKey.HEAT_PUMP_WORKLOAD.name). \
                    assign(variable=chosen_agent_name_to_view_2[:N] + "... Scenario 2")

                combined_heat_df = pd.concat([heat_pump_levels_agent_1_df, heat_pump_levels_agent_2_df],
                                             axis=0, join="outer").reset_index()
                heat_pump_chart = construct_agent_comparison_chart(combined_heat_df,
                                                                   title="Heat Pump Comparison",
                                                                   ylabel='Heat pump workload')
                st.altair_chart(heat_pump_chart, use_container_width=True, theme=None)

            if agent_1_type == "BatteryAgent":
                # make a battery storage level comparison graph
                storage_levels_agent_1_df = db_to_viewable_level_df_by_agent(
                    job_id=comparison_ids[0]['job_id'],
                    agent_guid=chosen_agent_name_to_view_1,
                    level_type=TradeMetadataKey.STORAGE_LEVEL.name). \
                    assign(variable=chosen_agent_name_to_view_1 + " Scenario 1")
                storage_levels_agent_2_df = db_to_viewable_level_df_by_agent(
                    job_id=comparison_ids[1]['job_id'],
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
