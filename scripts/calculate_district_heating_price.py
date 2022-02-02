import numpy as np
import pandas as pd

from calendar import monthrange, isleap

from tradingplatformpoc.bid import Action, Resource


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
    return 0.74 * monthly_peak_day_avg_consumption_kw


trades = pd.read_csv("../trades.csv", index_col=0)
external_heating_sells = trades.loc[(trades.action == Action.SELL.name) &
                                    (trades.resource == Resource.HEATING.name) &
                                    trades.by_external].copy()
external_heating_sells.index = pd.to_datetime(external_heating_sells.index)
external_heating_sells['month'] = external_heating_sells.index.month
external_heating_sells['day_of_month'] = external_heating_sells.index.day

jan_feb_avg_consumption_kw = external_heating_sells.loc[external_heating_sells.month <= 2].quantity.mean()
print('Average heating need for the microgrid in January-February was {:.4f} kW'.format(jan_feb_avg_consumption_kw))

monthly_sums = external_heating_sells.groupby('month')['quantity'].sum()
daily_sums = external_heating_sells.groupby(['month', 'day_of_month'], as_index=False)['quantity'].sum()
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
