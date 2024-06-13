import logging

from st_pages import add_indentation, show_pages_from_config

import streamlit as st

from tradingplatformpoc.app import footer
from tradingplatformpoc.app.app_comparison import ComparisonIds, construct_dump_comparison_chart, \
    construct_level_comparison_chart, get_keys_with_x_first, import_export_calculations, show_key_figures
from tradingplatformpoc.app.app_constants import AGGREGATION_LEVELS
from tradingplatformpoc.market.trade import TradeMetadataKey
from tradingplatformpoc.sql.agent.crud import get_agent_type
from tradingplatformpoc.sql.config.crud import get_all_agent_name_id_pairs_in_config, \
    get_all_finished_job_config_id_pairs_in_db
from tradingplatformpoc.sql.results.crud import get_results_for_job

logger = logging.getLogger(__name__)

show_pages_from_config("tradingplatformpoc/app/pages_config/pages.toml")
add_indentation()

job_id_per_config_id = get_all_finished_job_config_id_pairs_in_db()
if len(job_id_per_config_id) >= 2:
    first_col, second_col = st.columns(2)

    # Ensure that 'default' goes in the leftmost column by default, if it has been run.
    config_ids = get_keys_with_x_first(job_id_per_config_id, 'default')

    with first_col:
        chosen_config_id_to_view_1 = st.selectbox('Choose a first configuration to compare', config_ids)

    with second_col:
        chosen_config_id_to_view_2 = st.selectbox(
            'Choose a second configuration to compare',
            [key for key in config_ids if key != chosen_config_id_to_view_1])
            
    chosen_config_ids = [chosen_config_id_to_view_1, chosen_config_id_to_view_2]
    if None not in chosen_config_ids:
        comparison_ids = ComparisonIds(job_id_per_config_id, chosen_config_ids)
        pre_calculated_results_1 = get_results_for_job(comparison_ids.id_pairs[0].job_id)
        pre_calculated_results_2 = get_results_for_job(comparison_ids.id_pairs[1].job_id)
        show_key_figures(pre_calculated_results_1, pre_calculated_results_2)

        # Import export graph
        logger.info("Constructing import/export graph")
        with st.spinner("Constructing import/export graph"):
            aggregation_type = st.radio('Aggregation:', AGGREGATION_LEVELS, horizontal=True)
            imp_exp_chart = import_export_calculations(comparison_ids, aggregation_type[:1], 'sum')
            st.caption("Hold *Shift* and click on multiple variables in the legend to highlight them in the graph.")
            st.altair_chart(imp_exp_chart, use_container_width=True, theme=None)

        # Unused resource graphs
        with st.expander('Unused resources:'):
            logger.info("Constructing resource dump graphs")
            heat_dump_chart = construct_dump_comparison_chart(comparison_ids, TradeMetadataKey.HEAT_DUMP, "Heat")
            st.altair_chart(heat_dump_chart, use_container_width=True, theme=None)
            cool_dump_chart = construct_dump_comparison_chart(comparison_ids, TradeMetadataKey.COOL_DUMP, "Cooling")
            st.altair_chart(cool_dump_chart, use_container_width=True, theme=None)

        # Agent comparison
        st.subheader("Agent comparison graphs")
        first_col, second_col = st.columns(2)
        # The default "PVParkAgent" has nothing which will be shown here, so we exclude it from the lists. A bit hacky,
        # would want to change it if we remove/change this agent at some point.
        with first_col:
            agent_1_specs = get_all_agent_name_id_pairs_in_config(comparison_ids.id_pairs[0].config_id)
            agent_1_names = [name for name, uid in agent_1_specs.items()
                             if get_agent_type(uid) == "BlockAgent" and 'PVParkAgent' not in name]
            chosen_agent_name_to_view_1 = st.selectbox('Select an agent from the first configuration', agent_1_names)
            agent_1_type = get_agent_type(agent_1_specs.get(chosen_agent_name_to_view_1))
        with second_col:
            agent_2_specs = get_all_agent_name_id_pairs_in_config(comparison_ids.id_pairs[1].config_id)
            agent_2_names = [name for name, uid in agent_2_specs.items()
                             if get_agent_type(uid) == agent_1_type and 'PVParkAgent' not in name]
            chosen_agent_name_to_view_2 = st.selectbox('Select an agent from the second configuration', agent_2_names)

        logger.info(f"Creating a {agent_1_type} graph")
        with st.spinner(f"Creating a {agent_1_type} graph"):

            if not agent_2_names:
                st.markdown("There is no relevant agent in the second configuration")
            else:
                if agent_1_type not in ['GridAgent', 'HeatProducerAgent']:
                    # Make a heat pump workload comparison graph
                    heat_pump_comparison_chart = construct_level_comparison_chart(
                        comparison_ids, [chosen_agent_name_to_view_1, chosen_agent_name_to_view_2],
                        TradeMetadataKey.HP_HIGH_HEAT_PROD, "Output", "Heat pump high-temp heat output comparison")
                    if heat_pump_comparison_chart is None:
                        st.caption("No heat pumps for either of these agents.")
                    else:
                        st.caption("Click on a variable in the legend to highlight it in the graph.")
                        st.altair_chart(heat_pump_comparison_chart, use_container_width=True, theme=None)

                    # Make a battery storage level comparison graph
                    battery_comparison_chart = construct_level_comparison_chart(
                        comparison_ids, [chosen_agent_name_to_view_1, chosen_agent_name_to_view_2],
                        TradeMetadataKey.BATTERY_LEVEL, "Capacity [%]", "Battery charging level comparison")
                    if battery_comparison_chart is None:
                        st.caption("No batteries for either of these agents.")
                    else:
                        st.caption("Click on a variable in the legend to highlight it in the graph.")
                        st.altair_chart(battery_comparison_chart, use_container_width=True, theme=None)

                    # Make an acc tank storage level comparison graph
                    acc_tank_comparison_chart = construct_level_comparison_chart(
                        comparison_ids, [chosen_agent_name_to_view_1, chosen_agent_name_to_view_2],
                        TradeMetadataKey.ACC_TANK_LEVEL, "Capacity [%]", "Accumulator tank charging level comparison")
                    if acc_tank_comparison_chart is None:
                        st.caption("No accumulator tanks for either of these agents.")
                    else:
                        st.caption("Click on a variable in the legend to highlight it in the graph.")
                        st.altair_chart(acc_tank_comparison_chart, use_container_width=True, theme=None)

                    # Make BITES storage level comparison graphs
                    shallow_comparison_chart = construct_level_comparison_chart(
                        comparison_ids, [chosen_agent_name_to_view_1, chosen_agent_name_to_view_2],
                        TradeMetadataKey.SHALLOW_STORAGE_REL, "Capacity [%]", "Shallow BITES level comparison")
                    deep_comparison_chart = construct_level_comparison_chart(
                        comparison_ids, [chosen_agent_name_to_view_1, chosen_agent_name_to_view_2],
                        TradeMetadataKey.DEEP_STORAGE_REL, "Capacity [%]", "Deep BITES level comparison")
                    if shallow_comparison_chart is None:
                        st.caption("No building inertia thermal energy storage for either of these agents.")
                    else:
                        st.caption("Click on a variable in the legend to highlight it in the graph.")
                        st.altair_chart(shallow_comparison_chart, use_container_width=True, theme=None)
                        st.altair_chart(deep_comparison_chart, use_container_width=True, theme=None)

else:
    st.markdown('Too few scenarios to compare, set up a configuration in '
                '**Setup configuration** and run it in **Run simulation**.')

st.write(footer.html, unsafe_allow_html=True)
