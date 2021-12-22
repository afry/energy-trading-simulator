import pandas as pd
import json
import statsmodels.api as sm

from tradingplatformpoc.agent.building_agent import BuildingAgent

pd.options.mode.chained_assignment = None  # default='warn'

KWH_PER_YEAR_M2_ATEMP = 20  # According to Skanska: 20 kWh/year/m2 Atemp
PV_EFFICIENCY = 0.165


def main():
    # Load model
    # model = sm.load('./data/models/household_electricity_model.pickle')

    # Read in-data: Temperature and timestamps
    df_temp = pd.read_csv('./data/temperature_vetelangden.csv', names=['datetime', 'temperature'],
                          delimiter=';', header=0)
    df_inputs = create_inputs_df(df_temp)

    with open("../data/jonstaka.json", "r") as jsonfile:
        config_data = json.load(jsonfile)

    agents = []
    for agent in config_data["Agents"]:
        agent_type = agent["Name"]
        if agent_type == "BuildingAgent":
            agents.append(BuildingAgent(data_store_entity))


def create_inputs_df(df_temp):
    df_inputs = df_temp
    df_inputs['datetime'] = pd.to_datetime(df_inputs['datetime'])
    df_inputs = df_inputs.interpolate(method='linear')  # In case there are any missing values
    df_inputs['hour_of_day'] = df_inputs['datetime'].dt.hour + 1
    df_inputs['day_of_week'] = df_inputs['datetime'].dt.dayofweek + 1
    df_inputs['day_of_month'] = df_inputs['datetime'].dt.day
    df_inputs['month_of_year'] = df_inputs['datetime'].dt.month
    df_inputs.set_index('datetime', inplace=True)
    df_inputs['major_holiday'] = is_major_holiday_sweden(df_inputs['month_of_year'], df_inputs['day_of_month'])
    df_inputs['pre_major_holiday'] = is_day_before_major_holiday_sweden(df_inputs['month_of_year'],
                                                                        df_inputs['day_of_month'])
    return df_inputs


def is_major_holiday_sweden(month_of_year, day_of_month):
    # Christmas eve, Christmas day, Boxing day, New years day, epiphany, 1 may, national day.
    # Some moveable ones not included
    return ((month_of_year == 12) & (day_of_month == 24)) | \
           ((month_of_year == 12) & (day_of_month == 25)) | \
           ((month_of_year == 12) & (day_of_month == 26)) | \
           ((month_of_year == 1) & (day_of_month == 1)) | \
           ((month_of_year == 1) & (day_of_month == 6)) | \
           ((month_of_year == 5) & (day_of_month == 1)) | \
           ((month_of_year == 6) & (day_of_month == 6))


def is_day_before_major_holiday_sweden(month_of_year, day_of_month):
    return ((month_of_year == 12) & (day_of_month == 23)) | \
           ((month_of_year == 12) & (day_of_month == 31)) | \
           ((month_of_year == 1) & (day_of_month == 5)) | \
           ((month_of_year == 4) & (day_of_month == 30)) | \
           ((month_of_year == 6) & (day_of_month == 5))


def scale_electricity_consumption(unscaled_simulated_values_for_year, m2):
    current_yearly_sum = unscaled_simulated_values_for_year.sum()
    wanted_yearly_sum = m2 * KWH_PER_YEAR_M2_ATEMP
    return unscaled_simulated_values_for_year * (wanted_yearly_sum / current_yearly_sum)


if __name__ == '__main__':
    main()
