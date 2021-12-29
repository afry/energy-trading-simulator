import math

import numpy as np
import pandas as pd
import json
import statsmodels.api as sm

pd.options.mode.chained_assignment = None  # default='warn'

KWH_PER_YEAR_M2_ATEMP = 20  # According to Skanska: 20 kWh/year/m2 Atemp
PV_EFFICIENCY = 0.165
M2_PER_APARTMENT = 70

"""Currently this script generates household electricity consumption data, and rooftop PV production data, 
for BuildingAgents, no more, no less. """


def main():
    # Load model
    model = sm.load('./tradingplatformpoc/data/models/household_electricity_model.pickle')

    # Read in-data: Temperature and timestamps
    df_temp = pd.read_csv('./tradingplatformpoc/data/temperature_vetelangden.csv', names=['datetime', 'temperature'],
                          delimiter=';', header=0)
    df_temp['datetime'] = pd.to_datetime(df_temp['datetime'])
    df_irrd = pd.read_csv('./tradingplatformpoc/data/varberg_irradiation_W_m2_h.csv')
    df_irrd['datetime'] = pd.to_datetime(df_irrd['datetime'])
    df_inputs = create_inputs_df(df_irrd, df_temp)
    df_irrd.set_index('datetime', inplace=True)

    with open("./tradingplatformpoc/data/jonstaka.json", "r") as json_file:
        config_data = json.load(json_file)

    output_per_building = pd.DataFrame({'datetime': df_inputs.index})
    output_per_building.set_index('datetime', inplace=True)

    building_agents = []
    for agent in config_data["Agents"]:
        agent_type = agent["Type"]
        if agent_type == "BuildingAgent":
            building_agents.append(agent)
            pv_area = agent["RooftopPVArea"] if "RooftopPVArea" in agent else 0

            start_seed = agent['RandomSeed'] * 1000
            df_output = simulate_for_area(df_inputs, model, agent['GrossFloorArea'], start_seed)
            output_per_building[agent["Name"] + '_elec_cons'] = df_output.sum(axis=1)
            output_per_building[agent["Name"] + '_pv_prod'] = df_irrd * pv_area * PV_EFFICIENCY / 1000

    output_per_building.to_csv('./tradingplatformpoc/data/generated/mock.csv')


def simulate_for_area(df_inputs, model, gross_floor_area, start_seed):
    df_output = pd.DataFrame({'datetime': df_inputs.index})
    df_output.set_index('datetime', inplace=True)

    n_apartments = math.ceil(gross_floor_area / M2_PER_APARTMENT)

    for i in range(0, n_apartments):
        unscaled_simulated_values_for_apartment = simulate_series(df_inputs, start_seed + i, model)
        # Scale
        m2_for_this_apartment = M2_PER_APARTMENT if i < (n_apartments - 1) else \
            (gross_floor_area - M2_PER_APARTMENT * (n_apartments - 1))
        simulated_values_for_this_apartment = scale_electricity_consumption(unscaled_simulated_values_for_apartment,
                                                                            m2_for_this_apartment)
        df_output['apartment' + str(i)] = simulated_values_for_this_apartment
    return df_output


def simulate_series(input_df, rand_seed, model):
    """
    Runs simulations using "model" and "input_df", with "rand_seed" as the random seed (can be specified, so that the
    experiment becomes reproducible, and also when simulating several different apartments/houses, the simulations don't
    end up identical). The autoregressive parts of the model are calculated in calculate_adjustment_for_energy_prev.
    :param input_df: pd.DataFrame
    :param rand_seed: int
    :param model: statsmodels.regression.linear_model.RegressionResultsWrapper
    :return: pd.Series
    """
    np.random.seed(rand_seed)  # set random seed
    input_df['energy_prev'] = 0
    input_df['energy_prev'].iloc[0] = np.nan

    input_df['z_hat'] = model.predict(input_df)  # run regression with other_prev = 0, using the other_prev_start_dummy
    std_dev = np.sqrt(model.scale)  # store standard error
    input_df['simulated_log_energy_unscaled'] = np.nan  # y_t

    eps_vec = np.random.normal(0, std_dev, size=input_df.shape[0])

    # For t=0, z=y
    input_df['simulated_log_energy_unscaled'].iloc[0] = input_df['z_hat'].iloc[0] + eps_vec[0]

    # For t>0, y_t = max(0, zhat_t + beta * y_(t-1) + eps_t)
    for t in range(1, len(input_df)):
        energy_prev = np.exp(input_df['simulated_log_energy_unscaled'].iloc[t - 1])
        adjustment_for_prev = calculate_adjustment_for_energy_prev(model, energy_prev)
        input_df['simulated_log_energy_unscaled'].iloc[t] = input_df['z_hat'].iloc[t] + adjustment_for_prev + eps_vec[t]
    return np.exp(input_df['simulated_log_energy_unscaled'])


def calculate_adjustment_for_energy_prev(model, energy_prev):
    return model.params['np.where(np.isnan(energy_prev), 0, energy_prev)'] * energy_prev + \
           model.params['np.where(np.isnan(energy_prev), 0, np.power(energy_prev, 2))'] * np.power(energy_prev, 2) + \
           model.params['np.where(np.isnan(energy_prev), 0, np.minimum(energy_prev, 0.3))'] * np.minimum(energy_prev,
                                                                                                         0.3) + \
           model.params['np.where(np.isnan(energy_prev), 0, np.minimum(energy_prev, 0.7))'] * np.minimum(energy_prev,
                                                                                                         0.7)


def create_inputs_df(df_irrd, df_temp):
    df_inputs = df_temp.merge(df_irrd)
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
