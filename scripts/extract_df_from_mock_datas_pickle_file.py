import argparse

import pandas as pd

from tradingplatformpoc.generate_data.mock_data_utils import \
    get_elec_cons_key, get_hot_tap_water_cons_key, get_space_heat_cons_key
from tradingplatformpoc.sql.mock_data.crud import db_to_mock_data_df, get_mock_data_ids_for_agent


def extract_all_mock_data_for_agent(agent_id: str):
    """
    A function to examine the generated mock data.
    Goes through the stored mock data for a given agent, and saves to a data frame,
    so that one can easily compare different configurations.
    """
    mock_data_ids = get_mock_data_ids_for_agent(agent_id)

    comparison_df = pd.DataFrame()
    for mock_data_id in mock_data_ids:
        df_temp = db_to_mock_data_df(mock_data_id).to_pandas()
        comparison_df[mock_data_id + 'Elec'] = df_temp[get_elec_cons_key(agent_id)]
        comparison_df[mock_data_id + 'HotTapWater'] = df_temp[get_hot_tap_water_cons_key(agent_id)]
        comparison_df[mock_data_id + 'SpaceHeat'] = df_temp[get_space_heat_cons_key(agent_id)]
    return comparison_df


parser = argparse.ArgumentParser()
parser.add_argument("--agent_id", dest="agent_id", default="", help="Agent ID in database.", type=str)
args = parser.parse_args()

if __name__ == '__main__':
    df = extract_all_mock_data_for_agent(args.agent_id)
    df.to_csv('./agent_cons.csv')

# Run in terminal
# Ex: python scripts/extract_df_from_mock_datas_pickle_file.py --agent_id 6488dcf2-3a7c-44c2-be9c-51d23ea45f61
