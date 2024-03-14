from calendar import isleap, monthrange

import numpy as np

import pandas as pd

from tradingplatformpoc.market.trade import Action, Resource

PATH_TO_TRADES_CSV = "../results/trades.csv"

"""
This script calculates some numbers that are needed to exactly calculate the district heating cost, according to the
pricing model used by Varberg Energi. It is based on the trades specified in the PATH_TO_TRADES_CSV file. If the script
fails to run properly, double check that this path is indeed correct!
The script was used to gather numbers for the https://doc.afdrift.se/display/RPJ/District+heating+Varberg%3A+Pricing
Confluence page.
"""


def get_base_energy_price(month_of_year: int):
    if 5 <= month_of_year <= 9:
        return 0.33  # Cheaper in summer
    else:
        return 0.55


def get_yearly_grid_fee(jan_feb_hourly_avg_consumption_kw: float):
    """Based on Jan-Feb average hourly heating use."""
    if jan_feb_hourly_avg_consumption_kw < 50:
        return 1150 + 1113 * jan_feb_hourly_avg_consumption_kw
    elif jan_feb_hourly_avg_consumption_kw < 100:
        return 3063 + 1075 * jan_feb_hourly_avg_consumption_kw
    elif jan_feb_hourly_avg_consumption_kw < 200:
        return 8163 + 1025 * jan_feb_hourly_avg_consumption_kw
    elif jan_feb_hourly_avg_consumption_kw < 400:
        return 18375 + 975 * jan_feb_hourly_avg_consumption_kw
    else:
        return 33750 + 938 * jan_feb_hourly_avg_consumption_kw


def get_grid_fee_for_month(jan_feb_hourly_avg_consumption_kw: float, year: int, month_of_year: int):
    days_in_month = monthrange(year, month_of_year)[1]
    days_in_year = 366 if isleap(year) else 365
    fraction_of_year = days_in_month / days_in_year
    yearly_fee = get_yearly_grid_fee(jan_feb_hourly_avg_consumption_kw)
    return yearly_fee * fraction_of_year


def get_effect_fee(monthly_peak_day_avg_consumption_kw: float):
    """
    @param monthly_peak_day_avg_consumption_kw Calculated by taking the day during the month which has the highest
        heating energy use, and taking the average hourly heating use that day.
    """
    return 74 * monthly_peak_day_avg_consumption_kw


trades = pd.read_csv(PATH_TO_TRADES_CSV, index_col=0)
# all_heating_use = trades.loc[(trades.action == Action.SELL.name) &
#                              (trades.resource == Resource.HEATING.name) &
#                              trades.by_external].copy()
all_heating_use = trades.loc[(trades.action == Action.BUY.name)
                             & (trades.resource == Resource.HEATING.name)
                             & (trades.agent == 'ResidentialBlockAgentBC1')].copy()
all_heating_use.index = pd.to_datetime(all_heating_use.index)
all_heating_use['month'] = all_heating_use.index.month
all_heating_use['day_of_month'] = all_heating_use.index.day

jan_feb_avg_consumption_kw = all_heating_use.loc[all_heating_use.month <= 2].quantity.mean()
print('Average heating need for the microgrid in January-February was {:.4f} kW'.format(jan_feb_avg_consumption_kw))

monthly_sums = all_heating_use.groupby('month')['quantity'].to_numpy().sum()
daily_sums = all_heating_use.groupby(['month', 'day_of_month'], as_index=False)['quantity'].to_numpy().sum()
max_daily_demand_by_month = daily_sums.groupby('month')['quantity'].max()  # Unit kWh
max_daily_avg_demand_by_month = max_daily_demand_by_month / 24  # Unit is now kW

for month in np.arange(1, 13):
    max_daily_avg_demand_kw = max_daily_avg_demand_by_month[month]
    fixed_part = get_grid_fee_for_month(jan_feb_avg_consumption_kw, 2019, month) + \
        get_effect_fee(max_daily_avg_demand_kw)
    consumption_this_month = monthly_sums[month]
    marginal_part = get_base_energy_price(month) * consumption_this_month
    cost_for_month = marginal_part + fixed_part
    price_per_kwh_for_month = cost_for_month / consumption_this_month

    print('For month {} the maximum daily average consumption was {:.4f} kW'.format(month, max_daily_avg_demand_kw))
    # print(max_daily_avg_demand_kw)
